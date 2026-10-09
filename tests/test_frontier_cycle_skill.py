"""Offline safety/format regressions for the reusable cycle-maintenance skill."""
import contextlib
import datetime as dt
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/frontier-indexer-cycle-maintenance"
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name):
    spec = importlib.util.spec_from_file_location("frontier_skill_" + name, SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


common = load("common")
release = load("release")
host = load("host")
remote_host = load("remote_host")
checks = load("checks")
deploy = load("deploy")
IMAGE = "ghcr.io/algo-net/frontier-indexer:v9.0.0@sha256:" + "a" * 64
NOW = dt.datetime(2026, 10, 9, tzinfo=dt.timezone.utc)


def fixture():
    services = {}
    for i, name in enumerate(checks.CHAIN):
        predecessor = [] if i == 0 else [checks.CHAIN[i - 1] + ".service"]
        services[name] = {"requires": predecessor[:], "after": predecessor[:], "before": []}
    return {"services": services, "settings": {"indexerImage": IMAGE, "resetSchemaGeneration": 9,
            "firstCheckpoint": "123", "suiNetwork": "testnet", "ingestConcurrencyMax": 2}}


def check_report():
    return {"ok": True, "integration_ran": True, "source_fingerprint": "fresh",
            "expected": {"image": IMAGE, "generation": 9, "checkpoint": 123},
            "checks": [{"name": name, "exit": 0} for name in deploy.REQUIRED_CHECKS]}


def release_report():
    keys = ["stable_release", "latest_release", "seven_day_policy", "platform", "source_revision",
            "source_repository", "version_label", "contracts", "checkpoint", "environment_keys",
            "all_pipelines", "pipeline_file_loaded", "schema_search_path"]
    return {"ok": True, "checks": dict.fromkeys(keys, True), "image": IMAGE,
            "checkpoint": 123, "observed_at": NOW.isoformat(), "architecture": "amd64"}


class FormatTests(unittest.TestCase):
    def test_portable_frontmatter_and_progressive_references(self):
        text = (SKILL / "SKILL.md").read_text()
        frontmatter, body = text.split("---", 2)[1:]
        name = re.search(r"^name: (.+)$", frontmatter, re.M)[1]
        description = re.search(r"^description: (.+)$", frontmatter, re.M)[1]
        compatibility = re.search(r"^compatibility: (.+)$", frontmatter, re.M)[1]
        self.assertEqual(name, SKILL.name)
        self.assertRegex(name, r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
        self.assertLessEqual(len(name), 64)
        self.assertTrue(0 < len(description) <= 1024)
        self.assertLessEqual(len(compatibility), 500)
        self.assertIn("## When to use", body)
        self.assertIn("## When not to use", body)
        self.assertLess(len(body.split()), 2500)
        for reference in re.findall(r"\]\((references/[^)]+)\)", body):
            self.assertTrue((SKILL / reference).is_file())

    def test_public_help_never_launches_containers_or_deploys(self):
        for path in [SCRIPTS / (name + ".py") for name in ["release", "host", "checks", "deploy"]] + [ROOT / "tests/frontier_indexer_container_check.py"]:
            with self.subTest(script=path.name):
                result = subprocess.run([sys.executable, str(path), "--help"], text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)


    def test_integration_waits_for_network_not_bootstrap_socket(self):
        source = (ROOT / "tests/frontier_indexer_container_check.py").read_text()
        self.assertIn('"--entrypoint", "pg_isready", DATABASE', source)
        self.assertIn('"network database readiness"', source)
        self.assertNotIn('podman("exec", "frontier-timescaledb", "pg_isready"', source)

    def test_integration_waits_for_required_metric_families(self):
        source = (ROOT / "tests/frontier_indexer_container_check.py").read_text()
        self.assertIn('wait_for(dashboard_metrics_ready, "dashboard metric initialization")', source)
        self.assertIn("return expected <= names", source)

    def test_optimized_integration_is_refused_before_container_operations(self):
        result = subprocess.run([sys.executable, "-O", str(ROOT / "tests/frontier_indexer_container_check.py"),
                                 "--old-image", IMAGE, "--old-checkpoint", "123", "--database-image", IMAGE],
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn("assertions enabled", result.stderr)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.commit = "1" * 40
        self.config = json.dumps({"os": "linux", "architecture": "amd64", "config": {"Labels": {
            "org.opencontainers.image.source": "https://github.com/Algo-Net/Frontier-Indexer",
            "org.opencontainers.image.revision": self.commit, "org.opencontainers.image.version": "v9.0.0"}}}).encode()
        self.config_digest = release.digest(self.config)
        self.manifest = json.dumps({"config": {"digest": self.config_digest}}).encode()
        self.files = {
            "src/lib.rs": 'const TESTNET_WORLD_PACKAGES: &[&str] = &["0xaaa", "0xbbb"];',
            ".env.sample": "FIRST_CHECKPOINT=123\n",
            "src/config.rs": "\n".join('env = "' + key + '"' for key in ["SUI_NETWORK", "PACKAGES", "FIRST_CHECKPOINT", "INGEST_CONCURRENCY_MAX", "DB_SCHEMA"]),
            "src/main.rs": 'PipelineConfig::from_file(Path::new("./pipelines.toml")); search_path%3D run_migrations',
            "pipelines.toml": "[pipelines]\na = true\nb = true\n",
        }

    def inspect(self, published="2026-09-29T12:00:00Z", asset="0xaaa"):
        def github(path):
            if path == "releases/latest":
                return {"tag_name": "v9.0.0"}
            if path.startswith("releases/tags/"):
                return {"published_at": published, "draft": False, "prerelease": False}
            return {"object": {"type": "commit", "sha": self.commit}}

        def fetch(url, headers=None):
            if "/token?" in url:
                return b'{"token":"never-print-this-token"}'
            if "/manifests/" in url:
                return self.manifest
            return self.config

        with patch.object(release, "github", side_effect=github), patch.object(release, "fetch", side_effect=fetch), patch.object(release, "source", side_effect=lambda commit, path: self.files[path]):
            return release.inspect_release("v9.0.0", asset, "0xbbb", 123, now=NOW)

    def test_registry_source_contract_and_policy_success(self):
        report = self.inspect()
        self.assertTrue(report["ok"])
        self.assertTrue(report["image"].endswith(release.digest(self.manifest)))
        self.assertEqual(report["enabled_pipeline_count"], 2)
        self.assertNotIn("never-print-this-token", json.dumps(report))
        self.assertIn("not signature", report["provenance"])

    def test_young_release_or_wrong_contract_is_not_eligible(self):
        self.assertFalse(self.inspect(published="2026-10-08T12:00:00Z")["checks"]["seven_day_policy"])
        self.assertFalse(self.inspect(asset="0xccc")["checks"]["contracts"])

    def test_disabled_pipeline_requires_review(self):
        self.files["pipelines.toml"] = "[pipelines]\na = false\n"
        self.assertFalse(self.inspect()["checks"]["all_pipelines"])

    def test_digest_mismatch_refused(self):
        with patch.object(release, "fetch", return_value=b"{}"):
            with self.assertRaises(Exception):
                release.registry_object("blobs/sha256:" + "a" * 64, {}, "sha256:" + "a" * 64)


class LocalSafetyTests(unittest.TestCase):
    def test_image_requires_qualified_content_pin(self):
        self.assertEqual(common.pinned_image(IMAGE), IMAGE)
        for image in ["frontier-indexer:v9", "algo-net/frontier-indexer@sha256:" + "a" * 64,
                      "ghcr.io/algo-net/frontier-indexer:latest", "x@y\n" + IMAGE]:
            with self.assertRaises(common.MaintenanceError):
                common.pinned_image(image)

    def test_fingerprint_detects_source_drift_but_ignores_bytecode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ["src/playbook.yml", "src/inventory.yml", "scripts/play.sh", ".pre-commit-config.yaml", "tests/check.py"]:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("initial")
            first = common.source_fingerprint(root)
            (root / "tests/__pycache__").mkdir()
            (root / "tests/__pycache__/check.pyc").write_bytes(b"bytecode")
            self.assertEqual(common.source_fingerprint(root), first)
            (root / "tests/check.py").write_text("changed")
            self.assertNotEqual(common.source_fingerprint(root), first)

    def test_fixture_chain_and_expected_values(self):
        self.assertTrue(checks.validate_fixture(fixture(), IMAGE, 9, 123)["settings_match"])
        wrong = fixture()
        wrong["settings"]["resetSchemaGeneration"] = 8
        with self.assertRaises(Exception):
            checks.validate_fixture(wrong, IMAGE, 9, 123)
        missing = fixture()
        missing["services"][checks.CHAIN[-1]]["requires"] = []
        with self.assertRaises(Exception):
            checks.validate_fixture(missing, IMAGE, 9, 123)

    def test_fixture_cycle_refused(self):
        cycle = fixture()
        cycle["services"][checks.CHAIN[0]]["after"] = [checks.CHAIN[-1] + ".service"]
        with self.assertRaises(Exception):
            checks.validate_fixture(cycle, IMAGE, 9, 123)


class HostSafetyTests(unittest.TestCase):
    def test_marker_never_echoes_invalid_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "marker"
            self.assertIsNone(remote_host.marker_state(path)["generation"])
            for value in ["secret-password", "07", "-1", "", "9223372036854775808", "7\n8"]:
                path.write_text(value)
                report = remote_host.marker_state(path)
                self.assertFalse(report["valid"])
                self.assertIsNone(report["generation"])
                self.assertNotIn("secret-password", json.dumps(report))
            path.write_text("7\n")
            self.assertEqual(remote_host.marker_state(path)["generation"], 7)

    def test_inventory_reads_only_allowlisted_settings_and_no_rows(self):
        database = {"schemas": [{"schema": "indexer", "relations": 60}], "databases": ["postgres"],
                    "bookkeeping": [], "hypertable_schemas": [], "consumers": [{"client": "10.0.0.2", "connections": 1}],
                    "outside_dependency_count": 0, "outside_dependencies": []}
        current = {"image": IMAGE, "state": "running", "networks": {"test": {"IPAddress": "10.0.0.2"}}}
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            (state / "indexer.env").write_text("DB_PASSWORD=never-print-password\nFIRST_CHECKPOINT=123\nDB_SCHEMA=indexer\n")
            (state / "db-password").write_text("never-read-password-file")
            (state / "schema-reset-generation").write_text("7")
            with patch.object(remote_host, "STATE", state), patch.object(remote_host, "sql", return_value=database), patch.object(remote_host, "services", return_value={}), patch.object(remote_host, "command", return_value=json.dumps(current)):
                report = remote_host.inventory()
                self.assertFalse(report["review_required"])
                self.assertNotIn("never-print-password", json.dumps(report))
                self.assertNotIn("never-read-password-file", json.dumps(report))
                (state / "obsolete.dump").write_text("not-read")
                self.assertTrue(remote_host.inventory()["review_required"])
        self.assertIsNone(re.search(r"\b(DROP|DELETE|ALTER|TRUNCATE)\b", remote_host.INVENTORY_SQL))
        # PostgreSQL inet::text adds /32 or /128; host() matches Podman's plain IPs.
        self.assertIn("host(client_addr) AS client", remote_host.INVENTORY_SQL)

    def test_remote_failed_report_survives_without_raw_stderr(self):
        result = SimpleNamespace(returncode=1, stdout='{"ok":false,"checks":{"marker":false}}', stderr="secret-auth-debug")
        with patch.object(host, "capture", return_value=(result, 1)):
            report = host.remote("scetrov@10.229.10.2", {"mode": "inventory"}, 30)
            self.assertFalse(report["ok"])
            self.assertNotIn("secret-auth-debug", json.dumps(report))
        with self.assertRaises(Exception):
            host.remote("-oProxyCommand=unsafe", {}, 30)


class DeploySafetyTests(unittest.TestCase):
    def test_missing_integration_and_stale_evidence_are_refused(self):
        with patch.object(deploy, "source_fingerprint", return_value="fresh"):
            self.assertEqual(deploy.validate_evidence(check_report(), ROOT)["generation"], 9)
            missing = check_report()
            missing["integration_ran"] = False
            with self.assertRaises(Exception):
                deploy.validate_evidence(missing, ROOT)
        with patch.object(deploy, "source_fingerprint", return_value="changed"):
            with self.assertRaises(Exception):
                deploy.validate_evidence(check_report(), ROOT)

    def test_release_expiry_and_expected_image_are_refused(self):
        deploy.validate_release(release_report(), check_report()["expected"], now=NOW)
        old = release_report()
        old["observed_at"] = (NOW - dt.timedelta(days=2)).isoformat()
        with self.assertRaises(Exception):
            deploy.validate_release(old, check_report()["expected"], now=NOW)
        wrong = release_report()
        wrong["image"] = IMAGE.replace("a" * 64, "b" * 64)
        with self.assertRaises(Exception):
            deploy.validate_release(wrong, check_report()["expected"], now=NOW)

    def test_plan_only_and_execution_without_both_approvals_never_call_host(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "checks.json"
            upstream = Path(directory) / "release.json"
            evidence.write_text(json.dumps(check_report()))
            report = release_report()
            report["observed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
            upstream.write_text(json.dumps(report))
            base = ["deploy.py", "--checks-report", str(evidence), "--release-report", str(upstream)]
            for extra, expected_exit in [([], 0), (["--execute"], 1), (["--execute", "--approve-cycle-reset"], 1)]:
                with self.subTest(extra=extra), patch.object(sys, "argv", base + extra), patch.object(deploy, "repository", return_value=ROOT), patch.object(deploy, "source_fingerprint", return_value="fresh"), patch.object(deploy, "remote") as remote, patch.object(deploy, "run_wrapper") as wrapper, contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(deploy.main(), expected_exit)
                    remote.assert_not_called()
                    wrapper.assert_not_called()

    def test_wrapper_emits_phases_not_raw_sensitive_debug(self):
        process = SimpleNamespace(stdout=iter([
            "TASK [nixos : Apply NixOS configuration] ***\n",
            "debug: DB_PASSWORD=must-not-appear\n",
            "fatal: connection-string=must-not-appear\n",
            "PLAY RECAP ***\n",
            "habiki : ok=80 changed=10 unreachable=0 failed=0 skipped=2 rescued=0 ignored=0\n",
        ]), wait=lambda: 0)
        output = io.StringIO()
        with patch.object(deploy.subprocess, "Popen", return_value=process) as invoked, contextlib.redirect_stdout(output):
            self.assertEqual(deploy.run_wrapper(ROOT), 0)
        self.assertNotIn("must-not-appear", output.getvalue())
        self.assertEqual(invoked.call_args.args[0][1:], ["--limit", "habiki", "--tags", "frontier-indexer"])
        self.assertTrue(json.loads(output.getvalue().splitlines()[-1])["ok"])


if __name__ == "__main__":
    unittest.main()
