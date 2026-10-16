#!/usr/bin/env python3
"""Reconcile only Miniflux's role/database in the existing PostgreSQL container.

Run as a root systemd oneshot. SQL and secrets travel over stdin/environment,
never command arguments. Capture diagnostics so SQL containing passwords cannot
leak into the journal. Session logging is disabled before password statements.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

CONTAINER = "authentik-postgresql"
ADMIN = "authentik"

# Use psql's literal quoting, never interpolate the password into SQL in Python.
SQL = r"""
\set ON_ERROR_STOP on
SET log_statement = 'none';
SET log_min_error_statement = 'panic';
SET statement_timeout = '15s';
SET lock_timeout = '5s';
\getenv password MINIFLUX_DB_PASSWORD
SELECT 'CREATE ROLE miniflux LOGIN' WHERE NOT EXISTS (
  SELECT 1 FROM pg_roles WHERE rolname = 'miniflux'
) \gexec
ALTER ROLE miniflux WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOREPLICATION NOBYPASSRLS PASSWORD :'password';
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member = 'miniflux'::regrole)
  THEN RAISE EXCEPTION 'Unexpected Miniflux role membership'; END IF;
  IF EXISTS (SELECT 1 FROM pg_database WHERE datname = 'miniflux'
    AND datdba <> 'miniflux'::regrole)
  THEN RAISE EXCEPTION 'Unexpected Miniflux database owner'; END IF;
END $$;
SELECT 'CREATE DATABASE miniflux OWNER miniflux' WHERE NOT EXISTS (
  SELECT 1 FROM pg_database WHERE datname = 'miniflux'
) \gexec
REVOKE ALL ON DATABASE miniflux FROM PUBLIC;
\connect miniflux
SET log_statement = 'none';
SET log_min_error_statement = 'panic';
SET statement_timeout = '15s';
SET lock_timeout = '5s';
ALTER SCHEMA public OWNER TO miniflux;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
"""


def reconcile(password_file: Path, podman: str = "podman", attempts: int = 30) -> None:
    password = password_file.read_text().strip()
    if not password or "\x00" in password or password.lower().endswith("_placeholder"):
        raise ValueError("invalid database credential")
    ready = [podman, "exec", CONTAINER, "pg_isready", "-U", ADMIN, "-d", "postgres"]
    for attempt in range(attempts):
        result = subprocess.run(ready, capture_output=True, timeout=5, check=False)
        if result.returncode == 0:
            break
        if attempt + 1 == attempts:
            raise RuntimeError("database readiness deadline exceeded")
        time.sleep(2)
    # Podman --env NAME reads the value from its environment, not argv.
    env = dict(os.environ, MINIFLUX_DB_PASSWORD=password)
    subprocess.run(
        [podman, "exec", "-i", "--env", "MINIFLUX_DB_PASSWORD", CONTAINER,
         "psql", "-X", "--no-password", "-U", ADMIN, "-d", "postgres"],
        input=SQL, text=True, env=env, capture_output=True, check=True, timeout=60,
    )


def main() -> int:
    try:
        reconcile(Path(os.environ["CREDENTIALS_DIRECTORY"]) / "db-password")
    except (OSError, KeyError, ValueError, RuntimeError, subprocess.SubprocessError):
        print("Miniflux database setup failed (readiness, credential or reconciliation error); application startup blocked.", file=sys.stderr)
        return 1
    print("Miniflux database role and database reconciled; existing data retained.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
