"""Offline catalogue, API contract and additive reconciliation tests."""
import copy
import fcntl
import importlib.util
import json
import os
import stat
import struct
import subprocess
import sys
from urllib.error import HTTPError, URLError
from unittest.mock import patch
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("subscriptions", ROOT / "scripts/miniflux_subscriptions.py")
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


def entry(**overrides):
    return dict(title="A & <B>", category="Security & News", url="https://example.org/rss?a=1&b=2", enabled=True, **overrides)


class CatalogueTests(unittest.TestCase):
    def load(self, entries):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feeds.json"
            path.write_text(json.dumps(entries))
            return sync.load_catalogue(path)

    def test_catalogue_counts_after_operator_disabled_http403_sources(self):
        entries = sync.load_catalogue(ROOT / "config/miniflux/feeds.json")
        self.assertEqual(len(entries), 47)
        self.assertEqual(sum(e["enabled"] for e in entries), 37)
        blocked = {"https://blog.checkpoint.com/feed/", "https://securityboulevard.com/feed/"}
        for feed in (e for e in entries if e["url"] in blocked):
            self.assertFalse(feed["enabled"])
            self.assertIn("HTTP 403", feed["reason"])
        self.assertTrue(all(e["reason"] for e in entries if not e["enabled"]))
        zdnet, = [e for e in entries if "zdnet" in e["url"]]
        self.assertIn("General News", zdnet["title"])
        self.assertEqual(zdnet["category"], "General News")

    def test_invalid_schema(self):
        for value in (None, {}, [None], [{}], [dict(entry(), enabled=1)],
                      [dict(entry(), title="")], [dict(entry(), category=3)],
                      [dict(entry(), enabled=False)], [dict(entry(), aliases="bad")],
                      [dict(entry(), extra=True)]):
            with self.subTest(value=value), self.assertRaises(sync.SyncError):
                self.load(value)

    def test_bad_urls_are_rejected_without_echoing_secret(self):
        for url in ("file:///etc/passwd", "https:///rss", "https://u:secret@example.org/rss",
                    "https://example.org/rss?token=secret", "https://example.org/api-key/secret",
                    "https://example.org/rss#secret", "https://example.org:bad/rss",
                    "https://example.org/\nrss", "https://example.org/rss?X-Amz-Signature=secret"):
            with self.subTest(url=url), self.assertRaises(sync.SyncError) as caught:
                self.load([dict(entry(), url=url)])
            self.assertNotIn("secret", str(caught.exception))

    def test_duplicate_and_alias_ownership_includes_disabled(self):
        for entries in ([entry(), entry()], [dict(entry(), aliases=[entry()["url"]])],
                        [entry(), dict(entry(), url="https://other.org/rss", aliases=[entry()["url"]], enabled=False, reason="gone")]):
            with self.assertRaises(sync.SyncError):
                self.load(entries)

    def test_export_deterministic_escaped_grouped_enabled_only(self):
        entries = self.load([entry(), dict(entry(), url="https://other.org/rss", enabled=False, reason="gone"),
                             dict(entry(), title="Other", url="https://third.org/rss", category="A")])
        first = sync.export_opml(entries)
        self.assertEqual(first, sync.export_opml(list(reversed(entries))))
        root = ET.fromstring(first)
        self.assertEqual([e.attrib["text"] for e in root.findall("body/outline")], ["A", "Security & News"])
        feeds = root.findall("body/outline/outline")
        self.assertEqual(len(feeds), 2)
        self.assertEqual(feeds[1].attrib["xmlUrl"], entry()["url"])
        self.assertEqual(feeds[1].attrib["text"], entry()["title"])
        self.assertNotIn(b"other.org", first)


class FakeAPI:
    def __init__(self):
        self.categories = []
        self.feeds = []
        self.calls = []
        self.username = "scetrov"
        self.failure = None
        self.category_failure = None
        self.inventory_failure = False
        self.canonical = None

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method == "GET":
            if self.inventory_failure:
                raise sync.SyncError("inventory unavailable")
            return copy.deepcopy({"/v1/me": {"username": self.username},
                                  "/v1/categories": self.categories, "/v1/feeds": self.feeds}[path])
        if path == "/v1/categories":
            if self.category_failure == "before":
                raise sync.SyncError("timeout")
            category = {"id": len(self.categories) + 1, "title": payload["title"]}
            self.categories.append(category)
            if self.category_failure == "after":
                raise sync.SyncError("timeout")
            return category
        if path == "/v1/feeds":
            if self.failure == "auth":
                raise sync.FatalError("auth rejected")
            if self.failure == "before" and payload["feed_url"] == entry()["url"]:
                raise sync.SyncError("timeout")
            feed = {"id": len(self.feeds) + 1, "feed_url": self.canonical or payload["feed_url"],
                    "category": payload["category_id"], "settings": {"crawler": True}}
            self.feeds.append(feed)
            if self.failure == "after":
                raise sync.SyncError("timeout")
            if self.failure == "inventory":
                self.inventory_failure = True
            return {"feed_id": feed["id"]}
        raise AssertionError("unexpected mutation")

    def writes(self):
        return [call for call in self.calls if call[0] != "GET"]


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeAPI()
        self.messages = []

    def run_sync(self, entries=None, apply=True):
        return sync.reconcile(self.api, entries or [entry()], "scetrov", apply=apply, emit=self.messages.append)

    def test_plan_only_reads_and_disabled_never_created(self):
        self.assertEqual(self.run_sync(apply=False), 0)
        self.assertEqual(self.api.writes(), [])
        self.assertEqual(self.run_sync([dict(entry(), enabled=False, reason="gone")]), 0)
        self.assertEqual(self.api.writes(), [])

    def test_repeat_run_zero_writes_and_existing_state_unchanged(self):
        unmanaged = {"id": 30, "feed_url": "https://unmanaged.org/rss", "starred": [1], "read": [2]}
        self.api.feeds.append(unmanaged)
        self.assertEqual(self.run_sync(), 0)
        before = copy.deepcopy((self.api.categories, self.api.feeds))
        self.api.calls.clear()
        self.assertEqual(self.run_sync(), 0)
        self.assertEqual(self.api.writes(), [])
        self.assertEqual((self.api.categories, self.api.feeds), before)

    def test_wrong_identity_blocks_all_writes(self):
        self.api.username = "someone-else"
        with self.assertRaises(sync.FatalError):
            self.run_sync()
        self.assertEqual(self.api.writes(), [])

    def test_inventory_failures_block_all_writes(self):
        self.api.inventory_failure = True
        with self.assertRaises(sync.FatalError):
            self.run_sync()
        self.assertEqual(self.api.writes(), [])

    def test_alias_matches_without_title_or_settings_changes(self):
        original = {"id": 1, "feed_url": "http://old.org/rss", "title": "UI edit", "read": [1]}
        self.api.feeds = [copy.deepcopy(original)]
        self.assertEqual(self.run_sync([dict(entry(), aliases=[original["feed_url"]])]), 0)
        self.assertEqual(self.api.writes(), [])
        self.assertEqual(self.api.feeds, [original])

    def test_register_observed_canonical_url_is_recognized_without_writes(self):
        catalogue = sync.load_catalogue(ROOT / "config/miniflux/feeds.json")
        register, = [e for e in catalogue if e["url"] == "https://www.theregister.com/security/headlines.atom"]
        self.api.feeds = [{"id": 1, "feed_url": "https://api.theregister.com/api/v1/article?orderBy=published&site_id=2&remapper=rss&query=tag:security"}]
        self.assertEqual(self.run_sync([register]), 0)
        self.assertEqual(self.api.writes(), [])

    def test_title_alone_is_not_identity(self):
        self.api.feeds = [{"id": 3, "feed_url": "https://different.org/rss", "title": entry()["title"]}]
        self.assertEqual(self.run_sync(), 0)
        self.assertEqual(len(self.api.feeds), 2)

    def test_ambiguous_alias_blocks_entry(self):
        self.api.feeds = [{"id": 1, "feed_url": entry()["url"]}, {"id": 2, "feed_url": "https://old.org/rss"}]
        self.assertEqual(self.run_sync([dict(entry(), aliases=["https://old.org/rss"])]), 1)
        self.assertEqual(self.api.writes(), [])

    def test_ambiguous_categories_block_entry(self):
        self.api.categories = [{"id": n, "title": entry()["category"]} for n in (1, 2)]
        self.assertEqual(self.run_sync(), 1)
        self.assertEqual(self.api.writes(), [])

    def test_uncertain_feed_success_reread_not_retried(self):
        self.api.failure = "after"
        self.assertEqual(self.run_sync(), 0)
        self.assertEqual(len(self.api.writes()), 2)
        self.assertEqual(self.api.calls[-1][:2], ("GET", "/v1/feeds"))

    def test_uncertain_category_success_reread_not_retried(self):
        self.api.category_failure = "after"
        self.assertEqual(self.run_sync(), 0)
        self.assertEqual(len(self.api.writes()), 2)

    def test_unresolved_category_not_retried(self):
        self.api.category_failure = "before"
        self.assertEqual(self.run_sync(), 1)
        self.assertEqual(len(self.api.writes()), 1)
        self.assertEqual(self.api.feeds, [])

    def test_partial_failure_continues_independent_entries(self):
        self.api.failure = "before"
        self.assertEqual(self.run_sync([entry(), dict(entry(), url="https://working.org/rss")]), 1)
        self.assertEqual(len(self.api.feeds), 1)
        self.assertEqual(self.api.feeds[0]["feed_url"], "https://working.org/rss")
        self.assertEqual(len(self.api.writes()), 3)

    def test_auth_failure_mid_apply_stops_writes(self):
        self.api.failure = "auth"
        with self.assertRaises(sync.FatalError):
            self.run_sync([entry(), dict(entry(), url="https://other.org/rss")])
        self.assertEqual(len(self.api.writes()), 2)

    def test_inventory_failure_after_create_stops_writes(self):
        self.api.failure = "inventory"
        with self.assertRaises(sync.FatalError):
            self.run_sync([entry(), dict(entry(), url="https://other.org/rss")])
        self.assertEqual(len(self.api.writes()), 2)

    def test_unexpected_canonical_url_reported_not_guessed(self):
        self.api.canonical = "https://unexpected.org/rss"
        self.assertEqual(self.run_sync(), 1)
        self.assertIn("explicit alias", "\n".join(self.messages))
        self.assertEqual(len(self.api.feeds), 1)

    def test_invalid_inventory_stops_before_writes(self):
        self.api.feeds = [{"id": "1", "feed_url": entry()["url"]}]
        with self.assertRaises(sync.FatalError):
            self.run_sync()
        self.assertEqual(self.api.writes(), [])


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.credential = Path(self.directory.name) / "token"
        self.credential.write_text("private-test-token\n")
        self.credential.chmod(0o600)

    def test_credential_private_file_and_loopback_only(self):
        client = sync.API("http://127.0.0.1:8091", self.credential)
        self.assertEqual(client.token, "private-test-token")
        self.credential.chmod(0o644)
        with self.assertRaises(sync.FatalError):
            sync.API("http://127.0.0.1:8091", self.credential)
        for url in ("https://remote.org", "http://localhost:8091", "http://u@127.0.0.1", "http://127.0.0.1/path"):
            with self.assertRaises(sync.FatalError):
                sync.API(url, self.credential)

    def systemd_acl(self, uid=None, group_permissions=0):
        # Linux POSIX ACL: owner, named service user, owning group, mask, other.
        undefined = 0xffffffff
        entries = [(1, 4, undefined), (2, 4, os.geteuid() if uid is None else uid),
                   (4, group_permissions, undefined), (16, 4, undefined), (32, 0, undefined)]
        return struct.pack("<I", 2) + b"".join(struct.pack("<HHI", *e) for e in entries)

    def test_systemd_root_owned_named_user_acl_is_private(self):
        self.credential.chmod(0o440)
        metadata = list(self.credential.stat())
        metadata[4] = metadata[5] = 0  # systemd keeps credential ownership root:root.
        with patch.object(sync.os, "fstat", return_value=os.stat_result(metadata)), \
             patch.object(sync.os, "getxattr", return_value=self.systemd_acl()) as acl:
            client = sync.API("http://127.0.0.1:8091", self.credential)
            self.assertEqual(client.token, "private-test-token")
            self.assertEqual(acl.call_args.args[1], "system.posix_acl_access")

    def test_group_read_without_exclusive_service_acl_stays_rejected(self):
        self.credential.chmod(0o440)
        metadata = list(self.credential.stat())
        metadata[4] = metadata[5] = 0
        for acl in (b"", b"malformed", self.systemd_acl(uid=os.geteuid() + 1),
                    self.systemd_acl(group_permissions=4)):
            with self.subTest(acl=acl), \
                 patch.object(sync.os, "fstat", return_value=os.stat_result(metadata)), \
                 patch.object(sync.os, "getxattr", return_value=acl), self.assertRaises(sync.FatalError):
                sync.API("http://127.0.0.1:8091", self.credential)
        with patch.object(sync.os, "fstat", return_value=os.stat_result(metadata)), \
             patch.object(sync.os, "getxattr", side_effect=OSError("ACL unsupported")), \
             self.assertRaises(sync.FatalError):
            sync.API("http://127.0.0.1:8091", self.credential)

    def test_acl_does_not_allow_writable_world_readable_or_nonregular_credentials(self):
        for mode in (0o460, 0o444, 0o640, 0o450):
            metadata = list(self.credential.stat())
            metadata[0] = stat.S_IFREG | mode
            metadata[4] = metadata[5] = 0
            with self.subTest(mode=mode), \
                 patch.object(sync.os, "fstat", return_value=os.stat_result(metadata)), \
                 patch.object(sync.os, "getxattr", return_value=self.systemd_acl()), self.assertRaises(sync.FatalError):
                sync.API("http://127.0.0.1:8091", self.credential)

    def test_invalid_credentials_are_sanitized(self):
        for token in ("", "secret\nheader", "x" * 4097, "secret\x00", "sécret"):
            self.credential.write_text(token)
            with self.assertRaises(sync.FatalError) as caught:
                sync.API("http://127.0.0.1:8091", self.credential)
            self.assertNotIn(token, str(caught.exception)) if token else None

    def test_plan_and_apply_share_lock_before_api_access(self):
        lock_path = Path(self.directory.name) / "sync.lock"
        with lock_path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for operation in ("plan", "apply"):
                result = subprocess.run([
                    sys.executable, str(ROOT / "scripts/miniflux_subscriptions.py"), operation,
                    "--credential-file", str(self.credential), "--operator", "scetrov",
                    "--lock-file", str(lock_path),
                ], capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 1)
                self.assertIn("another plan/apply is running", result.stderr)
                self.assertNotIn("private-test-token", result.stderr + result.stdout)

    def test_execution_deadline_is_fatal(self):
        with self.assertRaises(sync.FatalError):
            sync.deadline_expired(None, None)

    def test_header_timeout_and_refused_redirect(self):
        client = sync.API("http://127.0.0.1:8091", self.credential, timeout=12)
        with patch.object(client.opener, "open", side_effect=URLError("private remote body")) as opened:
            with self.assertRaises(sync.SyncError) as caught:
                client.request("GET", "/v1/me")
            request = opened.call_args.args[0]
            self.assertEqual(request.get_header("X-auth-token"), "private-test-token")
            self.assertEqual(opened.call_args.kwargs["timeout"], 12)
            self.assertNotIn("private", str(caught.exception))
        with self.assertRaises(sync.FatalError):
            sync.RefuseRedirect().redirect_request(None, None, 302, "", {}, "https://remote.org")
        for code in (301, 302, 307, 308, 401, 403):
            with patch.object(client.opener, "open", side_effect=HTTPError("", code, "secret", {}, None)):
                with self.assertRaises(sync.FatalError) as caught:
                    client.request("GET", "/v1/me")
                self.assertNotIn("secret", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
