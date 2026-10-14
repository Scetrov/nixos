#!/usr/bin/env python3
"""One-off homelab PG16 -> PG17 maintenance, invoked by upgrade-databases.yml.

No passwords are printed. Dumps and cold copies stay root-only on the host.
Failure leaves services stopped; rollback is an explicit Ansible invocation.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import time

PG17 = "docker.io/library/postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24"
DATABASES = {
    "oncall-postgres": "oncall",
    "dtrack-db": "dtrack",
    "authentik-postgresql": "authentik",
}
CLIENTS = [
    "podman-oncall-engine", "podman-oncall-celery", "oncall-migrate",
    "podman-dtrack-apiserver", "podman-dtrack-frontend",
    "podman-authentik-server", "podman-authentik-worker",
]
SERVICES = CLIENTS + ["podman-oncall-redis"] + [f"podman-{n}" for n in DATABASES]


def run(*args, **kwargs):
    # stderr can contain database values; do not echo it through Ansible.
    kwargs.setdefault("stdout", subprocess.PIPE)
    return subprocess.run(args, check=True, stderr=subprocess.PIPE, **kwargs).stdout


def inspect(name):
    return json.loads(run("podman", "inspect", name))[0]


def mount_source(container, destination):
    return Path(next(m["Source"] for m in container["Mounts"]
                     if m["Destination"] == destination))


def stop_services(names):
    # Only stop units present on this host (celery may be disabled).
    for name in names:
        state = run("systemctl", "show", f"{name}.service", "-p", "LoadState", "--value").decode().strip()
        if state != "not-found":
            run("systemctl", "stop", f"{name}.service")


def wait_ready(name, user):
    for _ in range(120):
        try:
            run("podman", "exec", name, "pg_isready", "-U", user, "-d", "postgres")
            return
        except subprocess.CalledProcessError:
            time.sleep(1)
    raise RuntimeError("temporary Postgres did not become ready")


def restore(dump, destination, user, name):
    """Restore a complete dump into an isolated PG17 cluster, failing on SQL errors."""
    destination.mkdir(mode=0o700)
    env = dict(os.environ, POSTGRES_PASSWORD=secrets.token_urlsafe(32))
    run("podman", "run", "-d", "--name", name, "--network=none",
        "--env", "POSTGRES_PASSWORD", "--env", f"POSTGRES_USER={user}",
        "--env", "POSTGRES_DB=postgres", "-v", f"{destination}:/var/lib/postgresql/data",
        PG17, env=env)
    try:
        wait_ready(name, user)
        # initdb already created this one role. Preserve its ALTER ROLE/password
        # from pg_dumpall, but omit the otherwise duplicate CREATE ROLE statement.
        filtered = dump.with_suffix(".restore.sql")
        try:
            with dump.open("rb") as source, filtered.open("wb") as output:
                for line in source:
                    if line.rstrip() != f"CREATE ROLE {user};".encode():
                        output.write(line)
            with filtered.open("rb") as source:
                run("podman", "exec", "-i", name, "psql", "-X", "-v", "ON_ERROR_STOP=1",
                    "-U", user, "-d", "postgres", stdin=source)
            return run("podman", "exec", name, "psql", "-XAt", "-U", user, "-d", "postgres",
                       "-c", "SELECT datname FROM pg_database WHERE NOT datistemplate ORDER BY datname").decode()
        finally:
            filtered.unlink(missing_ok=True)
    finally:
        run("podman", "stop", name)
        run("podman", "rm", name)


def inventory():
    result = {}
    for name, user in DATABASES.items():
        c = inspect(name)
        data = mount_source(c, "/var/lib/postgresql/data")
        if (data / "PG_VERSION").read_text().strip() != "16":
            raise RuntimeError(f"{name}: expected an existing PG16 cluster; refusing to rerun")
        result[name] = {"data": str(data), "user": user}
    return result


def guard():
    """Normal host deployment must not activate PG17 over existing PG16 files."""
    paths = [Path("/var/lib/authentik/postgresql-data"),
             Path("/var/lib/dependency-track/postgresql-data")]
    volume = subprocess.run(["podman", "volume", "inspect", "oncall-postgres-data"],
                            capture_output=True, check=False)
    if volume.returncode == 0:
        paths.append(Path(json.loads(volume.stdout)[0]["Mountpoint"]))
    for path in paths:
        version = path / "PG_VERSION"
        if version.exists() and version.read_text().strip() != "17":
            raise SystemExit("Existing pre-PG17 data found. Run scripts/play.sh --limit habiki "
                             "--tags database-upgrade -- -e upgrade_confirm=true first.")
    print("No incompatible Postgres data found.")


def save_manifest(root, manifest):
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def migrate(root):
    databases = inventory()
    if root.exists():
        raise RuntimeError("backup directory already exists; choose a new run directory")
    run("podman", "pull", PG17)
    redis = inspect("oncall-redis")
    redis_source = mount_source(redis, "/data")
    # Reserve space for both cold copies and restored clusters before stopping apps.
    for entry in databases.values():
        size = int(run("du", "-sb", entry["data"]).split()[0])
        if shutil.disk_usage(entry["data"]).free < size * 3 + 1024**3:
            raise RuntimeError("insufficient free space for dump, cold copy and restore")
    root.mkdir(mode=0o700, parents=True)
    manifest = {"generation": str(Path("/run/current-system").resolve()),
                "databases": databases, "installed": [], "redis_source": str(redis_source)}
    save_manifest(root, manifest)
    run("nix-store", "--add-root", str(root / "previous-system"), "--indirect",
        "--realise", manifest["generation"])
    stop_services(CLIENTS)
    # SAVE is synchronous; the snapshot is also retained independently of the volume.
    run("podman", "exec", "oncall-redis", "redis-cli", "SAVE")
    shutil.copy2(redis_source / "dump.rdb", root / "dump.rdb")
    stop_services(["podman-oncall-redis"])
    for name, entry in databases.items():
        directory = root / name
        directory.mkdir(mode=0o700)
        dump = directory / "dump.sql"
        with dump.open("wb") as output:
            run("podman", "exec", "--user", "postgres", name,
                "pg_dumpall", "-U", entry["user"], stdout=output)
        if not dump.stat().st_size:
            raise RuntimeError("empty database dump")
        expected = run("podman", "exec", name, "psql", "-XAt", "-U", entry["user"], "-d", "postgres",
                       "-c", "SELECT datname FROM pg_database WHERE NOT datistemplate ORDER BY datname").decode()
        stop_services([f"podman-{name}"])
        run("cp", "-a", "--reflink=auto", entry["data"], str(directory / "cold-pg16"))
        restored = restore(dump, directory / "pg17", entry["user"], f"upgrade-{name}")
        if restored != expected:
            raise RuntimeError(f"{name}: restored database list differs")
    # No source data is replaced until all three isolated restores succeed.
    for name, entry in databases.items():
        source = Path(entry["data"])
        original = source.with_name(source.name + ".pg16-before-upgrade")
        if original.exists():
            raise RuntimeError("retained original already exists; refusing to overwrite")
        source.rename(original)
        # Record the original before the second rename, so rollback also covers interruption.
        manifest["installed"].append(name)
        save_manifest(root, manifest)
        (root / name / "pg17").rename(source)
    run("podman", "volume", "create", "oncall-redis-data")
    target = Path(run("podman", "volume", "inspect", "oncall-redis-data", "--format", "{{.Mountpoint}}").decode().strip())
    if any(target.iterdir()):
        raise RuntimeError("new Redis volume is not empty; refusing to overwrite")
    shutil.copy2(root / "dump.rdb", target / "dump.rdb")
    manifest["prepared"] = True
    save_manifest(root, manifest)
    print(f"Restored all three PG17 clusters; backups retained at {root} for at least 7 days.")


def rollback(root):
    manifest = json.loads((root / "manifest.json").read_text())
    stop_services(SERVICES)
    for name in manifest["installed"]:
        source = Path(manifest["databases"][name]["data"])
        original = source.with_name(source.name + ".pg16-before-upgrade")
        if not original.exists():
            raise RuntimeError("retained PG16 original missing")
        if source.exists():
            source.rename(source.with_name(source.name + f".failed-pg17-{int(time.time())}"))
        original.rename(source)
    run("nix-env", "--profile", "/nix/var/nix/profiles/system", "--set", manifest["generation"])
    run(manifest["generation"] + "/bin/switch-to-configuration", "switch")
    run("systemctl", "start", *[f"podman-{n}.service" for n in DATABASES], "podman-oncall-redis.service")
    # The old unit creates an anonymous Redis volume. Restore into that container
    # and restart the container itself (not the unit, which would replace it).
    stop_services(CLIENTS)
    if (root / "dump.rdb").exists():
        run("podman", "cp", str(root / "dump.rdb"), "oncall-redis:/data/dump.rdb")
        run("podman", "restart", "oncall-redis")
    for name in CLIENTS:
        state = run("systemctl", "show", f"{name}.service", "-p", "LoadState", "--value").decode().strip()
        if state != "not-found":
            run("systemctl", "start", f"{name}.service")
    manifest["installed"] = []
    save_manifest(root, manifest)
    print("Previous NixOS generation and PG16 data restored; backups retained.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["guard", "check", "migrate", "rollback"])
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.action == "guard":
            guard()
        elif args.action == "check":
            print(json.dumps(inventory()))
        elif args.backup_dir is None or not args.backup_dir.is_absolute():
            parser.error("an absolute --backup-dir is required")
        elif args.action == "migrate":
            migrate(args.backup_dir)
        else:
            rollback(args.backup_dir)
    except (subprocess.CalledProcessError, OSError, RuntimeError, ValueError, StopIteration) as exc:
        # Do not include SQL, connection details or subprocess output in failures.
        raise SystemExit(f"Migration stopped ({type(exc).__name__}); services may be stopped. "
                         "Keep the backup directory and use the documented rollback play.") from None


if __name__ == "__main__":
    main()
