"""Deterministic, network-free collector tests. Run with Python + jsonschema."""
import copy
import datetime as dt
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("collector", ROOT / "src/roles/nixos/files/etc/nixos/pkgs/github-sbom-collector.py")
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)
SOURCE = {
    "repository": "Scetrov/efctl", "repositoryId": 1166984576,
    "workflowId": 238717662, "event": "push", "branch": "main",
    "artifact": "cyclonedx-sbom-v1", "path": "bom.json",
    "project": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "version": "main",
}
BOM = {"bomFormat": "CycloneDX", "specVersion": "1.6", "version": 1}
RUN = {
    "id": 100, "run_number": 1, "run_attempt": 1,
    "repository": {"id": SOURCE["repositoryId"]},
    "head_repository": {"id": SOURCE["repositoryId"]},
    "workflow_id": SOURCE["workflowId"], "status": "completed",
    "conclusion": "success", "event": "push", "head_branch": "main",
    "head_sha": "a" * 40, "pull_requests": [],
    "run_started_at": "2026-10-19T00:00:00Z",
}


def archive(data=None, name="bom.json", mode=None, extra=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
        info = zipfile.ZipInfo(name)
        if mode is not None:
            info.external_attr = mode << 16
        bundle.writestr(info, json.dumps(BOM).encode() if data is None else data)
        if extra:
            bundle.writestr(extra, b"extra")
    return buffer.getvalue()


def artifact(run, data):
    return {
        "id": run["id"] + 1000, "name": SOURCE["artifact"],
        "size_in_bytes": len(data), "expired": False,
        "created_at": run["run_started_at"],
        "digest": "sha256:" + hashlib.sha256(data).hexdigest(),
        "workflow_run": {"id": run["id"], "repository_id": SOURCE["repositoryId"],
                         "head_repository_id": SOURCE["repositoryId"],
                         "head_sha": run["head_sha"], "head_branch": "main"},
    }


class FakeHttp:
    def __init__(self, runs=None, data=None):
        self.runs = copy.deepcopy([RUN] if runs is None else runs)
        self.data = archive() if data is None else data
        self.artifacts = {r["id"]: [artifact(r, self.data)] for r in self.runs}
        self.uploads = []
        self.fail_upload = False

    def pages(self, path, field):
        if field == "workflow_runs":
            return iter(self.runs)
        run = int(path.split("/runs/")[1].split("/")[0])
        return iter(self.artifacts[run])

    def download(self, repo, artifact_id):
        return self.data

    def upload(self, project, data):
        self.uploads.append((project, data))
        if self.fail_upload:
            raise collector.Failure("network_error")
        return "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.config = {"sources": [copy.deepcopy(SOURCE)]}
        self.state = {}
        self.saved = []
        # Business-logic fixtures use a minimal schema; official schema validation
        # is tested separately when SBOM_SCHEMA_DIR is supplied by the Nix fixture.
        self.schema = collector.Draft7Validator({
            "type": "object", "required": ["bomFormat", "specVersion", "version"],
            "properties": {"version": {"type": "integer", "minimum": 1}},
        })
        self.http = FakeHttp()

    def collect(self, report_only=False):
        return collector.collect(self.config, self.state,
                                 lambda s: self.saved.append(copy.deepcopy(s)),
                                 self.http, self.schema, report_only,
                                 dt.datetime(2026, 10, 19, tzinfo=dt.timezone.utc))

    def test_acceptance_then_repeat_and_restart_are_noops(self):
        self.assertEqual(self.collect()["uploaded"], 1)
        self.assertEqual(self.saved[0]["attempts"].popitem()[1], 1)
        record = self.state["accepted"][SOURCE["project"]]
        self.assertEqual(record["token"], "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
        self.state = json.loads(json.dumps(self.state))
        self.assertEqual(self.collect()["uploaded"], 0)
        self.assertEqual(len(self.http.uploads), 1)

    def test_trust_policy(self):
        mutations = [
            {"repository": {"id": 1}}, {"head_repository": {"id": 1}},
            {"workflow_id": 1}, {"status": "in_progress"},
            {"conclusion": "failure"}, {"event": "pull_request"},
            {"head_branch": "other"}, {"head_sha": "bad"},
            {"pull_requests": [{"id": 1}]}, {"run_attempt": 0},
        ]
        for change in mutations:
            with self.subTest(change=change):
                run = {**copy.deepcopy(RUN), **change}
                self.assertFalse(collector.trusted(run, SOURCE))
        self.assertTrue(collector.trusted(RUN, SOURCE))

    def test_artifacts_from_previous_attempt_or_other_source_rejected(self):
        a = artifact(RUN, self.http.data)
        for field, value in [("id", 9), ("repository_id", 9), ("head_repository_id", 9), ("head_sha", "b" * 40), ("head_branch", "other")]:
            changed = copy.deepcopy(a)
            changed["workflow_run"][field] = value
            self.assertFalse(collector.artifact_matches(changed, RUN, SOURCE))
        a["created_at"] = "2026-10-18T00:00:00Z"
        self.assertFalse(collector.artifact_matches(a, RUN, SOURCE))

    def test_expired_digest_and_ambiguous_artifact(self):
        for mutation in ["expired", "digest", "ambiguous"]:
            with self.subTest(mutation=mutation):
                self.http = FakeHttp()
                a = self.http.artifacts[100][0]
                if mutation == "expired":
                    a["expired"] = True
                elif mutation == "digest":
                    a["digest"] = "sha256:" + "0" * 64
                else:
                    self.http.artifacts[100].append(copy.deepcopy(a))
                result = self.collect()
                self.assertEqual(result["failed"], 1)
                self.assertEqual(result["expired"], 1 if mutation == "expired" else 0)
                self.assertEqual(result["rejected"], 0 if mutation == "expired" else 1)
                self.assertFalse(self.http.uploads)

    def test_missing_historical_artifact_does_not_block_newer_run(self):
        newer = {**copy.deepcopy(RUN), "id": 101, "run_number": 2}
        self.http = FakeHttp([RUN, newer])
        self.http.artifacts[100] = []
        result = self.collect()
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["uploaded"], 1)

    def test_stale_runs_never_uploaded(self):
        newer = {**copy.deepcopy(RUN), "id": 101, "run_number": 2}
        self.http = FakeHttp([newer])
        self.collect()
        self.http.runs.append(copy.deepcopy(RUN))
        self.assertEqual(self.collect()["uploaded"], 0)
        self.assertEqual(len(self.http.uploads), 1)

    def test_run_order(self):
        newer = {**copy.deepcopy(RUN), "id": 101, "run_number": 2}
        self.http = FakeHttp([newer, RUN])
        self.assertEqual(self.collect()["uploaded"], 2)
        self.assertEqual([s["accepted"][SOURCE["project"]]["run"] for s in self.saved if s["accepted"]], [100, 100, 101])

    def test_target_not_selected_by_payload(self):
        document = {**BOM, "metadata": {"component": {"name": "attacker", "version": "other"}}}
        self.http = FakeHttp(data=archive(json.dumps(document).encode()))
        self.assertEqual(self.collect()["uploaded"], 1)
        self.assertEqual(self.http.uploads[0][0], SOURCE["project"])

    def test_attempt_budget_is_durable_and_bounded(self):
        self.http.fail_upload = True
        for _ in range(5):
            self.assertEqual(self.collect()["failed"], 1)
        self.assertEqual(len(self.http.uploads), 3)
        self.assertFalse(self.state["accepted"])
        self.assertEqual(next(iter(self.state["attempts"].values())), 3)

    def test_crash_after_acceptance_before_checkpoint_is_ambiguous(self):
        def save(state):
            self.saved.append(copy.deepcopy(state))
            if state["accepted"]:
                raise OSError("simulated crash")
        with self.assertRaises(OSError):
            collector.collect(self.config, self.state, save, self.http, self.schema)
        self.assertEqual(len(self.http.uploads), 1)
        self.state = self.saved[0]  # The durable pre-submission intent survives.
        self.assertEqual(self.collect()["uploaded"], 1)
        self.assertEqual(len(self.http.uploads), 2)

    def test_report_only_never_downloads_or_writes(self):
        with patch.object(self.http, "download", side_effect=AssertionError("download")):
            result = collector.collect(
                self.config, self.state, lambda s: self.saved.append(s), self.http, self.schema,
                True, dt.datetime(2026, 10, 19, 1, tzinfo=dt.timezone.utc))
            self.assertEqual(result["eligible"], 1)
            self.assertEqual(result["backlog"], 1)
            self.assertEqual(result["backlog_age_seconds"], 3600)
        self.assertFalse(self.saved)
        self.assertFalse(self.http.uploads)

    def test_separate_configured_targets_and_redacted_journal(self):
        other = copy.deepcopy(SOURCE)
        other["project"] = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
        self.config["sources"].append(other)
        output = io.StringIO()
        with patch("sys.stdout", output):
            self.assertEqual(self.collect()["uploaded"], 2)
        self.assertEqual(set(self.state["accepted"]), {SOURCE["project"], other["project"]})
        self.assertNotIn("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", output.getvalue())
        self.assertNotIn("secret", output.getvalue())

    def test_target_version_change_requires_operator_recovery(self):
        self.collect()
        self.config["sources"][0]["version"] = "other"
        self.assertEqual(self.collect()["failed"], 1)
        self.assertEqual(len(self.http.uploads), 1)

    def test_internal_processing_failure_is_outside_collector_boundary(self):
        self.assertEqual(self.collect()["uploaded"], 1)
        # There is deliberately no processing-status request/API in FakeHttp.
        self.assertEqual(self.collect()["skipped"], 1)

    def test_hostile_archives_and_payloads(self):
        cases = [archive(name="../bom.json"), archive(name="/bom.json"),
                 archive(name="dir\\bom.json"), archive(extra="extra.txt"),
                 archive(mode=stat.S_IFLNK | 0o777), b"not zip",
                 archive(b'{"bomFormat":"CycloneDX","bomFormat":"other"}'),
                 archive(b'{"bomFormat":"CycloneDX","specVersion":"1.6","version":NaN}'),
                 archive(json.dumps({**BOM, "specVersion": "1.5"}).encode()),
                 archive(json.dumps({**BOM, "version": "invalid"}).encode()),
                 archive(b"[" * 1000 + b"]" * 1000)]
        for data in cases:
            with self.subTest(data=data[:20]):
                with self.assertRaises(collector.Failure):
                    collector.payload(data, SOURCE, self.schema)

    def test_size_limits(self):
        with patch.object(collector, "COMPRESSED_LIMIT", 1):
            with self.assertRaises(collector.Failure):
                collector.payload(archive(), SOURCE, self.schema)
        with patch.object(collector, "EXPANDED_LIMIT", 1):
            with self.assertRaises(collector.Failure):
                collector.payload(archive(), SOURCE, self.schema)

    def test_json_complexity_and_duplicate_keys(self):
        for data in [b'{"a":1,"a":2}', b"[" * 70 + b"0" + b"]" * 70]:
            with self.assertRaises(collector.Failure):
                collector.json_document(data)

    def test_config_policy(self):
        collector.validate_config(self.config)
        for key, value in [("event", "pull_request"), ("repository", "a/b/../../x"), ("path", "../x"), ("workflowId", 0)]:
            config = copy.deepcopy(self.config)
            config["sources"][0][key] = value
            with self.assertRaises(collector.Failure):
                collector.validate_config(config)
        self.config["sources"].append(copy.deepcopy(SOURCE))
        with self.assertRaises(collector.Failure):
            collector.validate_config(self.config)

    def test_state_is_atomic_and_private(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            collector.atomic_write(path, b"{}")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with patch.object(collector.os, "replace", side_effect=OSError("crash")):
                with self.assertRaises(OSError):
                    collector.atomic_write(path, b"bad")
            self.assertEqual(path.read_bytes(), b"{}")
            self.assertEqual(list(Path(directory).iterdir()), [path])

    @unittest.skipUnless(os.environ.get("SBOM_SCHEMA_DIR"), "set SBOM_SCHEMA_DIR to test packaged official schemas")
    def test_packaged_official_schema(self):
        schema = collector.validator(os.environ["SBOM_SCHEMA_DIR"])
        collector.payload(archive(), SOURCE, schema)
        document = {**BOM, "components": [{"type": "library", "name": "test", "licenses": [{"license": {"id": "MIT"}}]}]}
        collector.payload(archive(json.dumps(document).encode()), SOURCE, schema)
        with self.assertRaises(collector.Failure):
            collector.payload(archive(json.dumps({**BOM, "components": [{"type": "not-a-type"}]}).encode()), SOURCE, schema)


class BootstrapRegressionTests(unittest.TestCase):
    def test_force_password_change_is_not_mistaken_for_bad_credentials(self):
        from scripts.tests.run_github_sbom_upload_integration import bootstrap

        calls = []
        new_password = None

        def request(path, method, body, form):
            nonlocal new_password
            calls.append(path)
            if path.endswith("forceChangePassword"):
                self.assertEqual(body["password"], "admin")
                self.assertNotEqual(body["newPassword"], "admin")
                self.assertEqual(body["newPassword"], body["confirmPassword"])
                new_password = body["newPassword"]
                return 200, ""
            if new_password is None:
                raise urllib.error.HTTPError("http://fixture", 401, "Unauthorized", {}, io.BytesIO(b"FORCE_PASSWORD_CHANGE"))
            self.assertEqual(body["password"], new_password)
            return 200, "fixture-login-token"

        with patch("sys.stdout", io.StringIO()):
            self.assertEqual(bootstrap(request), "fixture-login-token")
        self.assertEqual(calls, ["/api/v1/user/login", "/api/v1/user/forceChangePassword", "/api/v1/user/login"])


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.http = collector.Http("secret-github", "secret-dtrack", "https://dtrack.example")

    def test_upload_maps_uuid_and_never_autocreates(self):
        token = str(uuid.uuid4())
        with patch.object(self.http, "request", return_value=(200, {}, json.dumps({"token": token}).encode())) as request:
            self.assertEqual(self.http.upload(SOURCE["project"], b"{}"), token)
        body = json.loads(request.call_args.kwargs["body"])
        self.assertEqual(body["project"], SOURCE["project"])
        self.assertIs(body["autoCreate"], False)

    def test_upload_rejection_and_missing_token_do_not_claim_acceptance(self):
        with patch.object(self.http, "request", return_value=(200, {}, b"{}")):
            with self.assertRaisesRegex(collector.Failure, "accepted_without_valid_token"):
                self.http.upload(SOURCE["project"], b"{}")
        with patch.object(self.http, "request", return_value=(400, {}, b"secret-body")):
            with self.assertRaisesRegex(collector.Failure, "^upload_not_accepted$"):
                self.http.upload(SOURCE["project"], b"{}")

    def test_redirect_does_not_forward_token(self):
        with patch.object(self.http, "github", return_value=(302, {"Location": "https://storage.blob.core.windows.net/path?sig=secret"}, b"")):
            with patch.object(self.http, "request", return_value=(200, {}, b"zip")) as request:
                self.assertEqual(self.http.download("Scetrov/efctl", 1), b"zip")
                self.assertEqual(request.call_args.args[1], {})

    def test_redirect_allowlist(self):
        for url in ["http://storage.blob.core.windows.net/x", "https://attacker.invalid/x", "https://storage.blob.core.windows.net.attacker.invalid/x", "https://user:pass@storage.blob.core.windows.net/x"]:
            with self.subTest(url=url), patch.object(self.http, "github", return_value=(302, {"Location": url}, b"")):
                with self.assertRaises(collector.Failure):
                    self.http.download("Scetrov/efctl", 1)

    def test_pagination_is_bounded_and_constructed_locally(self):
        row = {"id": 1}
        with patch.object(self.http, "github", side_effect=[(200, {"Link": "https://attacker.invalid"}, json.dumps({"artifacts": [row] * 100}).encode()), (200, {}, b'{"artifacts":[]}')]) as get:
            self.assertEqual(len(list(self.http.pages("/repos/a/b/artifacts", "artifacts"))), 100)
            self.assertIn("page=2", get.call_args.args[0])
        with patch.object(self.http, "github", return_value=(200, {}, json.dumps({"artifacts": [row] * 100}).encode())):
            with self.assertRaises(collector.Failure):
                list(self.http.pages("/repos/a/b/artifacts", "artifacts"))

    def test_rate_limit_and_error_redaction(self):
        err = urllib.error.HTTPError("https://secret-url", 429, "secret-body", {"Retry-After": "300"}, None)
        with patch.object(self.http.opener, "open", side_effect=err):
            with self.assertRaisesRegex(collector.Failure, "^rate_limited$"):
                self.http.github("/repos/a/b/actions/runs")
        err = urllib.error.HTTPError("https://secret-url", 503, "secret-body", {}, None)
        with patch.object(self.http.opener, "open", side_effect=err) as op, patch.object(collector.time, "sleep"):
            with self.assertRaisesRegex(collector.Failure, "^http_503$"):
                self.http.github("/repos/a/b/actions/runs")
            self.assertEqual(op.call_count, 3)


if __name__ == "__main__":
    unittest.main()
