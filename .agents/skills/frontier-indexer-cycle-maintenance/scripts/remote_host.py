"""Read-only remote payload used by host.py; CONFIG is injected as Python data."""
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.parse
import urllib.request

STATE = Path("/var/lib/frontier-indexer")
UNITS = ["frontier-indexer-db-preflight", "frontier-indexer-schema-reset",
         "podman-frontier-indexer", "podman-frontier-timescaledb"]
SAFE_KEYS = {"SUI_NETWORK", "FIRST_CHECKPOINT", "PACKAGES", "INGEST_CONCURRENCY_MAX", "DB_SCHEMA"}
INVENTORY_SQL = """
WITH schemas AS (
 SELECT n.nspname AS schema, count(c.oid) AS relations
 FROM pg_namespace n LEFT JOIN pg_class c ON c.relnamespace=n.oid AND c.relkind IN ('r','p','v','m')
 WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
 GROUP BY n.nspname ORDER BY n.nspname
), consumers AS (
 SELECT host(client_addr) AS client, count(*) AS connections
 FROM pg_stat_activity WHERE pid <> pg_backend_pid() AND client_addr IS NOT NULL
 GROUP BY client_addr ORDER BY client_addr
), dependencies AS (
 SELECT DISTINCT ns.nspname AS schema, pg_describe_object(d.classid,d.objid,d.objsubid) AS object
 FROM pg_depend d
 JOIN pg_class ref ON d.refclassid='pg_class'::regclass AND ref.oid=d.refobjid
 JOIN pg_namespace rn ON rn.oid=ref.relnamespace
 LEFT JOIN pg_class c ON d.classid='pg_class'::regclass AND c.oid=d.objid
 LEFT JOIN pg_constraint k ON d.classid='pg_constraint'::regclass AND k.oid=d.objid
 LEFT JOIN pg_proc p ON d.classid='pg_proc'::regclass AND p.oid=d.objid
 LEFT JOIN pg_rewrite w ON d.classid='pg_rewrite'::regclass AND w.oid=d.objid
 LEFT JOIN pg_class v ON v.oid=w.ev_class
 JOIN pg_namespace ns ON ns.oid=coalesce(c.relnamespace,k.connamespace,p.pronamespace,v.relnamespace)
 WHERE rn.nspname='indexer' AND ns.nspname <> 'indexer'
 AND ns.nspname !~ '^pg_' AND ns.nspname !~ '^_timescaledb'
)
SELECT json_build_object(
 'schemas', coalesce((SELECT json_agg(s) FROM schemas s),'[]'::json),
 'databases', (SELECT json_agg(datname ORDER BY datname) FROM pg_database WHERE NOT datistemplate),
 'bookkeeping', coalesce((SELECT json_agg(t) FROM
   (SELECT schemaname,tablename FROM pg_tables
    WHERE schemaname !~ '^pg_' AND schemaname !~ '^_timescaledb'
    AND (tablename ILIKE '%migration%' OR tablename ILIKE '%watermark%')
    ORDER BY schemaname,tablename LIMIT 20) t),'[]'::json),
 'hypertable_schemas', coalesce((SELECT json_agg(t) FROM
   (SELECT hypertable_schema,count(*) FROM timescaledb_information.hypertables
    GROUP BY hypertable_schema ORDER BY hypertable_schema) t),'[]'::json),
 'consumers', coalesce((SELECT json_agg(c) FROM consumers c),'[]'::json),
 'outside_dependency_count', (SELECT count(*) FROM dependencies),
 'outside_dependencies', coalesce((SELECT json_agg(d) FROM (SELECT * FROM dependencies LIMIT 20) d),'[]'::json)
);
"""


class RemoteError(Exception):
    pass


def command(args, optional=False):
    result = subprocess.run(args, text=True, capture_output=True, timeout=60)
    if result.returncode and not optional:
        raise RemoteError(f"Read-only operation failed: {args[0]} (exit {result.returncode}); raw output suppressed")
    return result.stdout if result.returncode == 0 else None


def sql(query):
    return json.loads(command(["podman", "exec", "frontier-timescaledb", "psql", "-U", "postgres", "-d", "postgres",
                               "-X", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-c", query]))


def marker_state(path):
    if not path.exists():
        return {"present": False, "valid": True, "generation": None}
    if path.stat().st_size > 20:
        return {"present": True, "valid": False, "generation": None}
    try:
        value = path.read_text(encoding="ascii")
        valid = bool(re.fullmatch(r"(?:0|[1-9][0-9]{0,18})\n?", value)) and int(value) <= 2**63 - 1
        return {"present": True, "valid": valid, "generation": int(value) if valid else None}
    except (UnicodeError, ValueError):
        return {"present": True, "valid": False, "generation": None}


def services():
    text = command(["systemctl", "show", *[unit + ".service" for unit in UNITS],
                    "-p", "Id,ActiveState,Result,ExecMainStartTimestampMonotonic,ExecMainExitTimestampMonotonic"])
    result = {}
    for block in text.strip().split("\n\n"):
        values = dict(line.split("=", 1) for line in block.splitlines() if "=" in line)
        if "Id" in values:
            result[values.pop("Id").removesuffix(".service")] = values
    return result


def inventory():
    template = '{"image":{{json .ImageName}},"state":{{json .State.Status}},"networks":{{json .NetworkSettings.Networks}}}'
    current = json.loads(command(["podman", "inspect", "--type", "container", "frontier-indexer", "--format", template]))
    current["ip_addresses"] = sorted(network.get("IPAddress", "") for network in current.pop("networks").values())
    settings = {}
    for line in (STATE / "indexer.env").read_text().splitlines():
        key, separator, value = line.partition("=")
        if separator and key in SAFE_KEYS:
            settings[key] = value
    known = {"timescaledb-data", "db-password", "indexer.env", "schema-reset-generation", "schema-reset-generation.lock"}
    artifacts = []
    for directory, children, files in os.walk(STATE, followlinks=False):
        relative = Path(directory).relative_to(STATE)
        if relative == Path("."):
            children[:] = [child for child in children if child != "timescaledb-data"]
        for name in children + files:
            path = str(relative / name)
            if path not in known:
                artifacts.append(path)
    database = sql(INVENTORY_SQL)
    infrastructure = {"indexer", "timescaledb_information", "timescaledb_experimental", "toolkit_experimental"}
    other = [item for item in database["schemas"] if item["relations"] and item["schema"] not in infrastructure
             and not item["schema"].startswith("_timescaledb")]
    external = [item for item in database["consumers"] if item["client"] not in current["ip_addresses"]]
    outside_bookkeeping = [item for item in database["bookkeeping"] if item["schemaname"] != "indexer"]
    marker = marker_state(STATE / "schema-reset-generation")
    return {"hostname": os.uname().nodename, "architecture": os.uname().machine, "container": current, "settings": settings,
            "marker": marker, "database": database,
            "services": services(), "extra_artifact_count": len(artifacts), "extra_artifacts": sorted(artifacts)[:20],
            "review_required": bool(other or external or outside_bookkeeping or artifacts or database["outside_dependency_count"] or not marker["valid"])}


def verify(report, config):
    progress = sql("SELECT json_build_object('pipelines',count(*),'min_checkpoint',min(checkpoint_hi_inclusive),"
                   "'max_checkpoint',max(checkpoint_hi_inclusive)) FROM indexer.watermarks;")
    migrations = sql("SELECT json_build_object('applied',count(*)) FROM indexer.__diesel_schema_migrations;")
    with urllib.request.urlopen("http://127.0.0.1:9184/metrics", timeout=15) as response:
        metrics = response.read().decode()
    metric_names = set(re.findall(r"^([A-Za-z_:][A-Za-z0-9_:]*)[ {]", metrics, re.M))
    query = urllib.parse.urlencode({"query": 'up{job="frontier-indexer"}'})
    with urllib.request.urlopen("http://127.0.0.1:9090/api/v1/query?" + query, timeout=15) as response:
        scrape = json.load(response)
    scrape_values = [item["value"][1] for item in scrape.get("data", {}).get("result", [])]
    journal = command(["journalctl", "-u", "podman-frontier-indexer.service", "--since", config["since"], "--no-pager", "-o", "cat"])
    errors = ["Failed to connect to database", "Failed to get connection for database setup",
              "Failed to run pending migrations", "Failed to create database schema"]
    setup_errors = sum(any(pattern in line for pattern in errors) for line in journal.splitlines())
    units = report["services"]
    preflight = units["frontier-indexer-db-preflight"]
    reset = units["frontier-indexer-schema-reset"]
    indexer = units["podman-frontier-indexer"]
    end_preflight = int(preflight["ExecMainExitTimestampMonotonic"])
    start_reset = int(reset["ExecMainStartTimestampMonotonic"])
    end_reset = int(reset["ExecMainExitTimestampMonotonic"])
    start_indexer = int(indexer["ExecMainStartTimestampMonotonic"])
    expected_repo, expected_digest = config["image"].split("@", 1)
    expected_repo = expected_repo.rsplit(":", 1)[0] if ":" in expected_repo.rsplit("/", 1)[-1] else expected_repo
    actual = report["container"]["image"].split("@", 1)
    actual_repo = actual[0].rsplit(":", 1)[0] if ":" in actual[0].rsplit("/", 1)[-1] else actual[0]
    missing = sorted(set(config["dashboard_metrics"]) - metric_names)
    checks = {
        "marker": report["marker"]["valid"] and report["marker"]["generation"] == config["generation"],
        "image": len(actual) == 2 and actual_repo == expected_repo and actual[1] == expected_digest,
        "services": all(unit["Result"] == "success" for unit in units.values())
        and indexer["ActiveState"] == "active" and units["podman-frontier-timescaledb"]["ActiveState"] == "active",
        "ordering": 0 < end_preflight <= start_reset <= end_reset <= start_indexer,
        "checkpoint_setting": report["settings"].get("FIRST_CHECKPOINT") == str(config["checkpoint"]),
        "runtime_settings": report["settings"].get("SUI_NETWORK") == "testnet"
        and report["settings"].get("PACKAGES") == "app,world"
        and report["settings"].get("DB_SCHEMA") == "indexer"
        and report["settings"].get("INGEST_CONCURRENCY_MAX") == "2",
        "progress": progress["pipelines"] > 0 and progress["min_checkpoint"] is not None
        and progress["max_checkpoint"] is not None and progress["min_checkpoint"] >= config["checkpoint"]
        and progress["max_checkpoint"] > config["checkpoint"],
        "migrations": migrations["applied"] > 0,
        "prometheus": scrape.get("status") == "success" and bool(scrape_values) and all(value == "1" for value in scrape_values),
        "dashboard_metrics": not missing, "database_setup_errors": setup_errors == 0,
    }
    return {"ok": all(checks.values()), "checks": checks, "marker": report["marker"],
            "image": report["container"]["image"], "progress": progress, "migrations": migrations,
            "metric_count": len(metric_names), "missing_dashboard_metrics": missing,
            "database_setup_error_count": setup_errors, "inventory_review_required": report["review_required"]}


def main():
    try:
        report = inventory()
        report = verify(report, CONFIG) if CONFIG["mode"] == "verify" else {"ok": True, **report}
        print(json.dumps(report, separators=(",", ":"), sort_keys=True))
        return 0 if report["ok"] else 1
    except Exception as error:
        message = str(error) if isinstance(error, RemoteError) else f"Read-only inspection failed ({type(error).__name__}); check readiness/access"
        print(json.dumps({"ok": False, "error": message}, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
