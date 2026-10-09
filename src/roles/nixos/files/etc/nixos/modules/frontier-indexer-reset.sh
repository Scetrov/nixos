#!/usr/bin/env bash
set -euo pipefail

# Called by the managed oneshot unit; never pass credentials as arguments.
if [ "$#" -ne 5 ]; then
    echo "Frontier Indexer schema reset: expected environment, marker, generation, image and network" >&2
    exit 1
fi
env_file=$1
marker=$2
generation=$3
image=$4
network=$5

# Hold the lock through durable marker publication, including equal-generation checks.
exec 9>"${marker}.lock"
flock -x 9

action=$(python3 - "$marker" "$generation" <<'PY'
import pathlib
import re
import sys

marker = pathlib.Path(sys.argv[1])
generation = sys.argv[2]

def parse(value):
    if not re.fullmatch(r"(?:0|[1-9][0-9]{0,18})\n?", value):
        raise ValueError("invalid generation")
    result = int(value)
    if result > 2**63 - 1:
        raise ValueError("generation out of range")
    return result

try:
    recorded = parse(marker.read_text(encoding="ascii")) if marker.exists() else None
    if not generation:
        if recorded is not None:
            raise ValueError("cannot disable reset with an existing generation marker")
        print("skip")
    else:
        requested = parse(generation)
        if recorded is not None and requested < recorded:
            raise ValueError("stale generation refused")
        print("skip" if requested == recorded else "reset")
except (ValueError, OSError) as error:
    print(f"Frontier Indexer schema reset refused: {error}", file=sys.stderr)
    sys.exit(1)
PY
)
if [ "$action" = skip ]; then
    echo "Frontier Indexer schema reset skipped: no new generation"
    exit 0
fi

if [ ! -s "$env_file" ]; then
    echo "Frontier Indexer schema reset failed: missing runtime environment" >&2
    exit 1
fi
set -a
# shellcheck disable=SC1090
. "$env_file"
set +a
for key in DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD DB_SCHEMA; do
    if [ -z "${!key:-}" ]; then
        echo "Frontier Indexer schema reset failed: required env key $key is empty" >&2
        exit 1
    fi
done
if [ "$DB_SCHEMA" != indexer ]; then
    echo "Frontier Indexer schema reset refused: unexpected schema" >&2
    exit 1
fi

# Ansible stops the old writer before switch; systemd orders all managed starts
# after this unit. Refuse an unsafe direct reset rather than stop/start a writer
# inside its own dependency transaction.
writers=$(podman ps --filter 'name=^frontier-indexer$' --format '{{.Names}}')
if [ -n "$writers" ]; then
    echo "Frontier Indexer schema reset refused: indexer writer is still running" >&2
    exit 1
fi

export PGPASSWORD="$DB_PASSWORD"
podman run -i --rm --network="$network" --env PGPASSWORD --entrypoint=psql \
    "$image" -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    -v ON_ERROR_STOP=1 -v schema="$DB_SCHEMA" -v owner="$DB_USER" <<'SQL'
BEGIN;
SELECT format('DROP SCHEMA IF EXISTS %I CASCADE', :'schema');
\gexec
SELECT format('CREATE SCHEMA %I AUTHORIZATION %I', :'schema', :'owner');
\gexec
COMMIT;
SQL

# fsync the replacement file and parent directory; failure prevents startup.
python3 - "$marker" "$generation" <<'PY'
import os
import pathlib
import sys
import tempfile

marker = pathlib.Path(sys.argv[1])
name = None
try:
    fd, name = tempfile.mkstemp(prefix=marker.name + ".", dir=marker.parent)
    with os.fdopen(fd, "w", encoding="ascii") as output:
        os.fchmod(output.fileno(), 0o640)
        output.write(sys.argv[2])
        output.flush()
        os.fsync(output.fileno())
    os.replace(name, marker)
    name = None
    directory = os.open(marker.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
finally:
    if name is not None:
        os.unlink(name)
PY

echo "Frontier Indexer schema reset applied generation $generation"
