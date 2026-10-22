"""Isolated API fixtures for discovery, ownership, recovery and secret hygiene."""
import copy
import contextlib
import fcntl
import io
import os
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "src/roles/nixos/files/etc/nixos/modules/forgejo-mirrors.py"
spec = importlib.util.spec_from_file_location("forgejo_mirrors", MODULE)
mirrors = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mirrors)
NOW = 1800000000
STAMP = "2027-01-15T08:00:00Z"  # Exactly NOW, independent of wall clock.


def source(repo_id=1, name="repo", owner="Scetrov", owner_id=10, **changes):
    result = {"id": repo_id, "name": name, "owner": {"login": owner, "id": owner_id},
              "private": False, "fork": False, "archived": False, "size": 42}
    result.update(changes)
    return result


def policy(owner="Scetrov", owner_id=10, namespace="gh-Scetrov", namespace_id=100, pattern="*"):
    return {"owner": owner, "ownerId": owner_id, "namespace": namespace,
            "namespaceId": namespace_id, "pattern": pattern}


class FakeGitHub(mirrors.API):
    def __init__(self, repos, policies):
        self.token = ""
        self.repos = repos
        self.users = {p["owner"]: {"id": p["ownerId"], "type": "Organization" if p["owner"] == "storytold" else "User"} for p in policies}
        self.calls = []
        self.missing = {}

    def request(self, method, path, payload=None):
        self.calls.append((method, path))
        if path.startswith("/repositories/"):
            repo_id = int(path.rsplit("/", 1)[1])
            return self.missing.get(repo_id, next((r for r in self.repos if r["id"] == repo_id), None))
        if "/repos?" not in path:
            return self.users.get(path.rsplit("/", 1)[1])
        parts = path.split("?")[0].split("/")
        repos = self.repos if parts[1] == "user" else [r for r in self.repos if r["owner"]["login"] == parts[2]]
        page = int(path.split("page=")[-1])
        return copy.deepcopy(repos[(page - 1) * 100:page * 100])


class FakeForgejo:
    def __init__(self, policies):
        self.orgs = {p["namespace"]: {"id": p["namespaceId"], "visibility": "private"} for p in policies}
        self.repos = {}
        self.posts = []
        self.failure = None

    def request(self, method, path, payload=None):
        if method == "GET":
            if path.startswith("/orgs/"):
                return self.orgs.get(path.rsplit("/", 1)[1])
            return copy.deepcopy(self.repos.get(path.removeprefix("/repos/")))
        self.posts.append(copy.deepcopy(payload))
        if self.failure == "before":
            raise mirrors.MirrorError("transport_failure")
        destination = payload["repo_owner"] + "/" + payload["repo_name"]
        repo = {"id": len(self.repos) + 200, "private": True, "mirror": True,
                "owner": {"id": self.orgs[payload["repo_owner"]]["id"]},
                "description": payload["description"], "original_url": payload["clone_addr"],
                "mirror_updated": STAMP}
        self.repos[destination] = repo
        if self.failure == "after":
            raise mirrors.MirrorError("transport_failure")
        return copy.deepcopy(repo)


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.policies = [policy()]
        self.config = {"policies": self.policies, "reportOnly": False, "mirrorInterval": "1h",
                       "staleAfterSeconds": 10800, "lfsVerified": True}
        self.github = FakeGitHub([source()], self.policies)
        self.forgejo = FakeForgejo(self.policies)
        self.state = {"version": 1, "sources": {}, "lastSuccess": 0}
        self.saved = []

    def run_reconcile(self):
        return mirrors.Reconciler(self.config, self.github, self.forgejo, self.state,
                                  lambda: self.saved.append(copy.deepcopy(self.state)), now=NOW).run()

    def statuses(self, report):
        return [r["status"] for r in report["rows"]]

    def test_create_repeat_and_new_source(self):
        self.assertEqual(self.statuses(self.run_reconcile()), ["created"])
        self.assertNotIn("destinationId", self.saved[0]["sources"]["1"])
        self.assertEqual(self.statuses(self.run_reconcile()), ["healthy"])
        self.github.repos.append(source(2, "second"))
        self.assertEqual(self.statuses(self.run_reconcile()), ["healthy", "created"])
        self.assertEqual(len(self.forgejo.posts), 2)
        self.assertEqual(self.state["lastSuccess"], NOW)
        payload = self.forgejo.posts[0]
        self.assertEqual(payload["service"], "git")
        self.assertTrue(payload["lfs"] and payload["private"] and payload["mirror"])
        self.assertNotIn("auth_password", payload)

    def test_all_requested_patterns_case_insensitive_and_multiple_pages(self):
        self.policies[:] = [policy(), policy("RichardSlater", 11, "gh-RichardSlater", 101), policy("storytold", 12, "gh-storytold", 102, "*craft")]
        self.github = FakeGitHub([source(i, "repo" + str(i)) for i in range(1, 102)] + [
            source(201, "other", "RichardSlater", 11), source(202, "AniCraft", "storytold", 12),
            source(203, "not-a-match", "storytold", 12)], self.policies)
        self.forgejo = FakeForgejo(self.policies)
        report = self.run_reconcile()
        self.assertEqual(self.statuses(report).count("created"), 103)
        self.assertEqual(self.statuses(report).count("excluded"), 1)
        self.assertIn(("GET", "/users/Scetrov/repos?type=owner&per_page=100&page=2"), self.github.calls)
        self.assertTrue(any("/orgs/storytold/repos" in p for _, p in self.github.calls))

    def test_eligibility_defaults_and_explicit_opt_in(self):
        for field, option in [("fork", "includeForks"), ("archived", "includeArchived"), ("private", "includePrivate")]:
            with self.subTest(field=field):
                self.setUp()
                self.github.repos[0][field] = True
                self.assertEqual(self.statuses(self.run_reconcile()), ["excluded"])
                self.policies[0][option] = True
                self.config["privateAuthVerified"] = True
                self.github.token = "runtime-only"
                self.assertEqual(self.statuses(self.run_reconcile()), ["created"])
                if field == "private":
                    self.assertTrue(any(p.startswith("/user/repos?") for _, p in self.github.calls))
                    self.assertNotIn(self.github.token, json.dumps(self.state))
                    self.assertNotIn(self.github.token, json.dumps(self.run_reconcile()))

    def test_report_only_has_no_remote_or_ownership_writes(self):
        self.config["reportOnly"] = True
        self.assertEqual(self.statuses(self.run_reconcile()), ["planned"])
        self.assertEqual(self.forgejo.posts, [])
        self.assertEqual(self.saved, [])
        self.assertEqual(self.state["sources"], {})

    def test_namespace_collision_missing_private_and_id(self):
        for org in [None, {"id": 101, "visibility": "private"}, {"id": 100, "visibility": "public"}]:
            with self.subTest(org=org):
                self.forgejo.orgs["gh-Scetrov"] = org
                self.assertEqual(self.statuses(self.run_reconcile()), ["namespace_not_authorized"])
                self.assertEqual(self.forgejo.posts, [])

    def test_planned_destinations_cannot_collide(self):
        self.policies.append(policy("RichardSlater", 11, "gh-Scetrov", 100))
        self.github = FakeGitHub([source(), source(2, "repo", "RichardSlater", 11)], self.policies)
        self.assertEqual(self.statuses(self.run_reconcile()), ["planned_destination_collision"] * 2)
        self.assertEqual(self.forgejo.posts, [])

    def test_unrelated_destination_never_adopted(self):
        self.forgejo.repos["gh-Scetrov/repo"] = {"id": 200}
        self.assertEqual(self.statuses(self.run_reconcile()), ["destination_collision"])
        self.assertEqual(self.forgejo.posts, [])
        self.assertEqual(self.state["sources"], {})

    def test_destination_replacement_visibility_and_source_changes(self):
        self.run_reconcile()
        for field, value, expected in [("id", 999, "destination_identity_review"), ("private", False, "destination_boundary_review"), ("original_url", "https://github.com/unrelated/repo.git", "destination_source_review")]:
            with self.subTest(field=field):
                repo = self.forgejo.repos["gh-Scetrov/repo"]
                old = repo[field]
                repo[field] = value
                self.assertEqual(self.statuses(self.run_reconcile()), [expected])
                repo[field] = old
        self.assertEqual(len(self.forgejo.posts), 1)

    def test_rename_transfer_visibility_delete_and_policy_change_preserve_data(self):
        for change in ["rename", "transfer", "private", "delete", "policy", "archived"]:
            with self.subTest(change=change):
                self.setUp()
                self.run_reconcile()
                original = copy.deepcopy(self.state["sources"])
                if change == "rename":
                    self.github.repos[0]["name"] = "renamed"
                elif change == "transfer":
                    self.github.repos[0]["owner"] = {"id": 99, "login": "new-owner"}
                elif change == "private":
                    self.github.repos[0]["private"] = True
                elif change == "delete":
                    self.github.repos = []
                elif change == "policy":
                    self.policies[0]["pattern"] = "nomatch"
                else:
                    self.github.repos[0]["archived"] = True
                self.assertGreater(self.run_reconcile()["errors"], 0)
                self.assertEqual(self.state["sources"], original)
                self.assertEqual(len(self.forgejo.repos), 1)
                self.assertEqual(len(self.forgejo.posts), 1)

    def test_restart_recovers_committed_post_without_duplicate(self):
        self.forgejo.failure = "after"
        self.assertEqual(self.statuses(self.run_reconcile()), ["transport_failure"])
        self.state = copy.deepcopy(self.saved[-1])
        self.forgejo.failure = None
        self.assertEqual(self.statuses(self.run_reconcile()), ["healthy"])
        self.assertEqual(len(self.forgejo.posts), 1)
        self.assertIn("destinationId", self.state["sources"]["1"])

    def test_uncertain_uncommitted_post_needs_review_not_blind_retry(self):
        self.forgejo.failure = "before"
        self.run_reconcile()
        self.forgejo.failure = None
        self.assertEqual(self.statuses(self.run_reconcile()), ["pending_import_review"])
        self.assertEqual(len(self.forgejo.posts), 1)

    def test_pending_marker_cannot_adopt_unrelated_repository(self):
        self.forgejo.failure = "after"
        self.run_reconcile()
        self.forgejo.repos["gh-Scetrov/repo"]["description"] = "unrelated"
        self.assertEqual(self.statuses(self.run_reconcile()), ["destination_collision"])

    def test_individual_failure_does_not_block_other_sources(self):
        self.github.repos.append(source(2, "second"))
        self.forgejo.repos["gh-Scetrov/repo"] = {"id": 200}
        report = self.run_reconcile()
        self.assertEqual(self.statuses(report), ["destination_collision", "created"])
        self.assertEqual(self.state["lastSuccess"], 0)

    def test_lfs_and_private_auth_are_fail_closed(self):
        self.config["lfsVerified"] = False
        self.assertEqual(self.statuses(self.run_reconcile()), ["lfs_unverified"])
        self.assertEqual(self.forgejo.posts, [])
        self.assertEqual(self.state["sources"], {})

    def test_stale_unknown_and_metrics(self):
        self.run_reconcile()
        repo = self.forgejo.repos["gh-Scetrov/repo"]
        repo["mirror_updated"] = "2020-01-01T00:00:00Z"
        report = self.run_reconcile()
        self.assertEqual(self.statuses(report), ["mirror_stale"])
        output = mirrors.metrics(report, self.state, NOW)
        self.assertIn('forgejo_mirrors_repository_error{destination="gh-Scetrov/repo"} 1', output)
        self.assertIn('forgejo_mirrors_sync_age_seconds{destination="gh-Scetrov/repo"}', output)
        repo["mirror_updated"] = "unknown"
        self.assertEqual(self.statuses(self.run_reconcile()), ["mirror_status_unknown"])

    def test_atomic_state_reload_and_invalid_state_rejection(self):
        self.run_reconcile()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            mirrors.atomic_write(path, json.dumps(self.state))
            self.assertEqual(mirrors.load_state(path), self.state)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            path.write_text("invalid")
            with self.assertRaisesRegex(mirrors.MirrorError, "invalid_state"):
                mirrors.load_state(path)


class MainTests(unittest.TestCase):
    def test_runtime_secrets_reports_and_nonoverlapping_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            creds = root / "credentials"
            creds.mkdir()
            secret = os.urandom(24).hex()
            (creds / "forgejo").write_text(secret)
            config = {"policies": [policy()], "reportOnly": False, "mirrorInterval": "1h",
                      "staleAfterSeconds": 10800, "lfsVerified": True}
            (root / "config.json").write_text(json.dumps(config))
            github = FakeGitHub([source()], config["policies"])
            forgejo = FakeForgejo(config["policies"])
            argv = [str(MODULE), "--config", str(root / "config.json"), "--state-dir", directory,
                    "--metrics-file", str(root / "metrics.prom")]
            output = io.StringIO()
            with mock.patch.dict(os.environ, {"CREDENTIALS_DIRECTORY": str(creds)}), \
                    mock.patch("sys.argv", argv), mock.patch.object(mirrors, "API", side_effect=[github, forgejo]), \
                    mock.patch.object(mirrors.time, "time", return_value=NOW), contextlib.redirect_stdout(output):
                self.assertEqual(mirrors.main(), 0)
            report = json.loads((root / "report.json").read_text())
            self.assertEqual(report["eligibleSizeKiB"], 42)
            self.assertNotIn(secret, output.getvalue() + (root / "ownership.json").read_text() + json.dumps(report))
            with (root / "lock").open("a") as lock, mock.patch("sys.argv", argv), contextlib.redirect_stdout(output):
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.assertEqual(mirrors.main(), 1)
            self.assertIn("concurrent run refused", output.getvalue())

    def test_fatal_diagnostics_suppress_exception_details(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text("{}")
            output = io.StringIO()
            argv = [str(MODULE), "--config", str(root / "config.json"), "--state-dir", directory,
                    "--metrics-file", str(root / "metrics.prom")]
            with mock.patch("sys.argv", argv), mock.patch.object(mirrors, "load_state", side_effect=OSError("sensitive-upstream-body")), contextlib.redirect_stderr(output):
                self.assertEqual(mirrors.main(), 1)
            self.assertNotIn("sensitive-upstream-body", output.getvalue())
            self.assertIn("forgejo_mirrors_errors 1", (root / "metrics.prom").read_text())


class HTTPTests(unittest.TestCase):
    def test_retries_quota_deferral_redirects_and_secret_redaction(self):
        statuses = []
        received = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                received.append(self.headers.get("Authorization"))
                status, headers = statuses.pop(0)
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(b'{"message":"sensitive-upstream-body"}')
            do_POST = do_GET
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            sleeps = []
            api = mirrors.API("http://127.0.0.1:" + str(server.server_port), "runtime-token", sleep=sleeps.append)
            statuses[:] = [(503, {}), (200, {})]
            self.assertEqual(api.request("GET", "/test")["message"], "sensitive-upstream-body")
            self.assertEqual(sleeps, [1])
            statuses[:] = [(403, {"X-RateLimit-Remaining": "0", "Retry-After": "120"})]
            with self.assertRaisesRegex(mirrors.MirrorError, "^rate_limited$"):
                api.request("GET", "/test")
            statuses[:] = [(302, {"Location": "http://example.invalid/steal"})]
            with self.assertRaisesRegex(mirrors.MirrorError, "^http_302$"):
                api.request("GET", "/test")
            statuses[:] = [(503, {}), (200, {})]
            with self.assertRaisesRegex(mirrors.MirrorError, "^http_503$"):
                api.request("POST", "/test", {})
            self.assertEqual(len(statuses), 1)
            self.assertTrue(all(value == "Bearer runtime-token" for value in received))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_bounded_transport_retry(self):
        api = mirrors.API("http://127.0.0.1:1", sleep=lambda _: None)
        with mock.patch.object(api.opener, "open", side_effect=OSError("secret")) as opened:
            with self.assertRaisesRegex(mirrors.MirrorError, "^transport_failure$"):
                api.request("GET", "/test")
            self.assertEqual(opened.call_count, 3)


if __name__ == "__main__":
    unittest.main()
