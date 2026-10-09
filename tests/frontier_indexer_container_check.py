"""Opt-in, rootless Podman integration check; uses no production mounts or ports.

Run with --old-image, --old-checkpoint, and --database-image (all images pinned).
New image/checkpoint/generation come from Habiki's evaluated declarations.
The reserved container names must be absent in the caller's rootless namespace.
Only containers and the network created by this run are removed.
"""
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
RESET = ROOT / "src/roles/nixos/files/etc/nixos/modules/frontier-indexer-reset.sh"
def qualified_pin(image):
    registry = image.split("/", 1)[0]
    return bool(re.fullmatch(r"[a-z0-9.-]+(?::[0-9]+)?/[A-Za-z0-9_./:-]+@sha256:[a-f0-9]{64}", image)) and (
        "." in registry or ":" in registry or registry == "localhost"
    )


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--old-image", required=True)
parser.add_argument("--old-checkpoint", type=int, required=True)
parser.add_argument("--database-image", required=True)
args = parser.parse_args()
if not __debug__:
    parser.error("Integration checks require assertions enabled; unset PYTHONOPTIMIZE and do not use -O")
OLD_INDEXER = args.old_image
DATABASE = args.database_image
if args.old_checkpoint < 0:
    parser.error("--old-checkpoint must be nonnegative")
for image in (OLD_INDEXER, DATABASE):
    if not qualified_pin(image):
        parser.error("All images must be fully qualified and SHA256-pinned")


def run(args, check=True, **kwargs):
    result = subprocess.run(args, text=True, capture_output=True, timeout=180, **kwargs)
    if check and result.returncode:
        # Test passwords are randomly generated; redact them even in failure output.
        raise RuntimeError(f"Command {args[0]} failed ({result.returncode}): "
                           f"{result.stderr[-2000:].replace(password, '[redacted]')}")
    return result


def podman(*args, **kwargs):
    return run(["podman", *args], **kwargs)


def sql(query):
    return podman("exec", "frontier-timescaledb", "psql", "-U", "postgres",
                  "-d", "postgres", "-X", "-A", "-t", "-v", "ON_ERROR_STOP=1",
                  "-c", query).stdout.strip()


def wait_for(predicate, description, seconds=90):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(2)
    raise RuntimeError(f"Timed out waiting for {description}")


def start_indexer(image, first_checkpoint):
    return podman("run", "-d", "--name", "frontier-indexer", "--network", network,
                  "--env-file", str(envfile), "--env", "SUI_NETWORK=testnet",
                  "--env", "PACKAGES=app,world", "--env", "INGEST_CONCURRENCY_MAX=2",
                  "--env", f"FIRST_CHECKPOINT={first_checkpoint}", image)


password = secrets.token_hex(24)
settings = json.loads(run(["nix-instantiate", "--eval", "--strict", "--json", "-E",
                           "(import ./tests/frontier-indexer-eval.nix).settings"], cwd=ROOT).stdout)
INDEXER = settings["indexerImage"]
CHECKPOINT = int(settings["firstCheckpoint"])
GENERATION = str(settings["resetSchemaGeneration"])
if CHECKPOINT < 0 or not GENERATION.isdecimal() or not 1 <= int(GENERATION) <= 2**63 - 1:
    parser.error("Declared cycle checkpoint/generation is invalid")
if not qualified_pin(INDEXER):
    parser.error("Declared new image must be fully qualified and SHA256-pinned")
PREVIOUS = str(int(GENERATION) - 1)
network = "frontier-cycle-test-" + uuid.uuid4().hex[:12]
created = []
network_created = False
assert podman("info", "--format", "{{.Host.Security.Rootless}}").stdout.strip() == "true", "Rootless Podman required"
for name in ("frontier-timescaledb", "frontier-indexer"):
    result = podman("container", "exists", name, check=False)
    if result.returncode == 0:
        raise RuntimeError(f"Refusing to touch existing container {name}")
    assert result.returncode == 1, "Cannot safely determine container existence"

with tempfile.TemporaryDirectory(prefix="frontier-cycle-test-") as temporary:
    directory = Path(temporary)
    envfile = directory / "indexer.env"
    marker = directory / "generation"
    passwordfile = directory / "db-password"
    envfile.write_text(f"DB_HOST=frontier-timescaledb\nDB_PORT=5432\nDB_NAME=postgres\n"
                       f"DB_USER=postgres\nDB_PASSWORD={password}\nDB_SCHEMA=indexer\n")
    envfile.chmod(0o600)
    passwordfile.write_text(password)
    passwordfile.chmod(0o600)

    def reset(generation=GENERATION, check=True):
        return run(["bash", str(RESET), str(envfile), str(marker), generation,
                    DATABASE, network], check=check)

    try:
        # Build the actual Nix-generated preflight, changing only test paths/network/image.
        scripts = run(["nix-build", "tests/frontier-indexer-eval.nix", "-A", "scripts", "--no-out-link"], cwd=ROOT).stdout.strip()
        preflight = (Path(scripts) / "frontier-indexer-db-preflight").read_text()
        preflight = preflight.replace("/var/lib/frontier-indexer/indexer.env", str(envfile))
        preflight = preflight.replace("/var/lib/frontier-indexer/db-password", str(passwordfile))
        preflight = preflight.replace("--network=" + settings["network"], f"--network={network}")
        preflight = preflight.replace(settings["timescaleImage"], DATABASE)
        preflight_path = directory / "preflight.sh"
        preflight_path.write_text(preflight)
        podman("network", "create", network)
        network_created = True
        # No host ports or persistent production volumes are attached.
        podman("run", "-d", "--name", "frontier-timescaledb", "--network", network,
               "--env", "POSTGRES_DB=postgres", "--env", "POSTGRES_USER=postgres",
               "--env", "POSTGRES_PASSWORD", DATABASE,
               env=dict(os.environ, POSTGRES_PASSWORD=password))
        created.append("frontier-timescaledb")
        # Match production: the temporary init server's Unix socket is not network readiness.
        wait_for(lambda: podman("run", "--rm", "--network", network, "--entrypoint", "pg_isready", DATABASE,
                                "-h", "frontier-timescaledb", "-p", "5432", "-U", "postgres", check=False).returncode == 0,
                 "network database readiness")
        run(["bash", str(preflight_path)])
        print("PASS authenticated generated preflight")

        sql("CREATE SCHEMA unrelated; CREATE TABLE unrelated.keep (id int PRIMARY KEY); INSERT INTO unrelated.keep VALUES (42);")
        # Run the supplied previous-cycle image with its recorded checkpoint.
        start_indexer(OLD_INDEXER, str(args.old_checkpoint))
        created.append("frontier-indexer")
        wait_for(lambda: sql("SELECT to_regclass('indexer.watermarks') IS NOT NULL;") == "t", "previous-cycle migrations")
        marker.write_text(PREVIOUS)
        refused = reset(check=False)
        assert refused.returncode != 0 and "still running" in refused.stderr
        assert marker.read_text() == PREVIOUS
        print("PASS running previous-cycle writer blocks reset")
        podman("stop", "-t", "20", "frontier-indexer")
        podman("rm", "frontier-indexer")
        created.remove("frontier-indexer")

        # Repair mismatched credentials before reset using the actual generated preflight.
        sql("ALTER USER postgres WITH PASSWORD 'deliberately-wrong-test-password';")
        repaired = run(["bash", str(preflight_path)])
        assert "after synchronizing" in repaired.stdout
        print("PASS credential mismatch repair before reset")
        reset()
        assert marker.read_text() == GENERATION
        assert sql("SELECT to_regclass('indexer.watermarks') IS NULL;") == "t"
        assert sql("SELECT id FROM unrelated.keep;") == "42"
        print("PASS schema reset removes old bookkeeping and preserves unrelated rows")

        # Real database reset errors preserve the marker and transaction state.
        marker.write_text(PREVIOUS)
        original = envfile.read_text()
        envfile.write_text(original.replace("DB_PASSWORD=" + password, "DB_PASSWORD=wrong-test-password"))
        assert reset(check=False).returncode != 0
        assert marker.read_text() == PREVIOUS
        envfile.write_text(original)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: reset(), range(2)))
        assert all(result.returncode == 0 for result in results)
        assert sum("applied generation" in result.stdout for result in results) == 1
        print("PASS failed authentication and serialized real resets")

        start_indexer(INDEXER, str(CHECKPOINT))
        created.append("frontier-indexer")
        wait_for(lambda: sql("SELECT to_regclass('indexer.watermarks') IS NOT NULL;") == "t", "new-cycle migrations")
        print("PASS declared pinned image migrations")
        # Actual watermark advancement is required, not just an active container.
        wait_for(lambda: sql(f"SELECT count(*) FROM indexer.watermarks WHERE checkpoint_hi_inclusive > {CHECKPOINT};") not in ("0", ""), "new-cycle checkpoint advancement", seconds=180)
        print("Watermark summary:", sql("SELECT count(*), min(checkpoint_hi_inclusive), max(checkpoint_hi_inclusive) FROM indexer.watermarks;"))
        sql(f"CREATE TABLE indexer.restart_sentinel (id int PRIMARY KEY); INSERT INTO indexer.restart_sentinel VALUES ({GENERATION});")
        reset()  # Equal generation must preserve all newly indexed state while writer runs.
        # Rebuild and execute the generated reset wrapper, then restart the real image.
        rebuilt = run(["nix-build", "tests/frontier-indexer-eval.nix", "-A", "scripts", "--no-out-link"], cwd=ROOT).stdout.strip()
        reset_wrapper = (Path(rebuilt) / "frontier-indexer-schema-reset").read_text()
        reset_wrapper = reset_wrapper.replace("/var/lib/frontier-indexer/indexer.env", str(envfile))
        reset_wrapper = reset_wrapper.replace("/var/lib/frontier-indexer/schema-reset-generation", str(marker))
        reset_wrapper = reset_wrapper.replace(settings["timescaleImage"], DATABASE)
        # The generated wrapper's final argument is the dedicated network name.
        reset_wrapper = reset_wrapper.replace("\n  " + settings["network"] + "\n", "\n  " + network + "\n")
        wrapper_path = directory / "reset-wrapper.sh"
        wrapper_path.write_text(reset_wrapper)
        podman("stop", "-t", "20", "frontier-indexer")
        podman("rm", "frontier-indexer")
        created.remove("frontier-indexer")
        run(["bash", str(wrapper_path)])
        start_indexer(INDEXER, str(CHECKPOINT))
        created.append("frontier-indexer")
        wait_for(lambda: sql("SELECT count(*) FROM pg_stat_activity WHERE client_addr IS NOT NULL;") not in ("0", ""), "restarted indexer database connection")
        assert sql("SELECT id FROM indexer.restart_sentinel;") == GENERATION
        for bad_generation in (PREVIOUS, "garbage"):
            assert reset(bad_generation, check=False).returncode != 0
        assert sql("SELECT id FROM unrelated.keep;") == "42"
        assert sql("SELECT count(*) FROM indexer.watermarks;") not in ("0", "")
        print("PASS checkpoint initialization/progress, equal restart, stale/invalid guard, unrelated preservation")
        # Metrics are exposed only inside the isolated network.
        def fetch_metrics():
            return podman("run", "--rm", "--network", network, "--entrypoint", "python3", DATABASE,
                          "-c", "import urllib.request; print(urllib.request.urlopen('http://frontier-indexer:9184/metrics',timeout=10).read().decode())",
                          check=False)

        dashboard = (ROOT / "terraform/dashboards/frontier-indexer.json").read_text()
        expected = set(re.findall(r"\bfrontier_indexer_[A-Za-z0-9_]+", dashboard))
        # Chain-head metrics are supplied by the unchanged external exporter.
        expected = {name for name in expected if not name.startswith("frontier_indexer_chain_head_")}

        def dashboard_metrics_ready():
            response = fetch_metrics()
            if response.returncode:
                return False
            names = set(re.findall(r"^([A-Za-z_:][A-Za-z0-9_:]*)[ {]", response.stdout, flags=re.MULTILINE))
            return expected <= names

        # HTTP readiness precedes lazy processor/concurrency metric initialization.
        wait_for(dashboard_metrics_ready, "dashboard metric initialization")
        metrics = fetch_metrics().stdout
        assert "checkpoint" in metrics and "frontier_indexer_db" in metrics
        exported = set(re.findall(r"^([A-Za-z_:][A-Za-z0-9_:]*)[ {]", metrics, flags=re.MULTILINE))
        assert expected <= exported, f"Missing dashboard metrics: {sorted(expected - exported)}"
        print("PASS pinned image metrics and existing dashboard metric names available")
    except Exception:
        if "frontier-indexer" in created:
            logs = podman("logs", "--tail", "30", "frontier-indexer", check=False)
            print("Indexer diagnostic log tail:", (logs.stdout + logs.stderr).replace(password, "[redacted]")[-4000:])
        raise
    finally:
        cleanup_errors = []
        for name in reversed(created):
            if podman("rm", "-f", "--volumes", name, check=False).returncode:
                cleanup_errors.append(name)
        if network_created and podman("network", "rm", network, check=False).returncode:
            cleanup_errors.append(network)
        if cleanup_errors:
            raise RuntimeError("Failed to remove owned test resources: " + ", ".join(cleanup_errors))
