"""Offline tests for dedicated GitHub App credentials across installations."""
import base64
import copy
import datetime as dt
import json
import unittest
from unittest.mock import Mock, patch

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from scripts.tests.test_github_sbom_collector import SOURCE, collector


NOW = 1800000000


def decode(part):
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


class GitHubAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.pem = cls.key.private_bytes(serialization.Encoding.PEM,
                                      serialization.PrivateFormat.PKCS8,
                                      serialization.NoEncryption())

    def setUp(self):
        self.sources = [copy.deepcopy(SOURCE), {
            **SOURCE, "repository": "AnotherOrg/project", "repositoryId": 42,
            "project": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        }]
        self.app_config = {"appId": 123, "installationIds": [111, 222]}
        self.installations = {"Scetrov/efctl": 111, "AnotherOrg/project": 222}
        self.expiry = NOW + 3600
        self.permissions = {"actions": "read", "metadata": "read"}
        self.calls = []

    def response(self, url, headers, limit, method="GET", body=None):
        self.calls.append((url, headers, method, body))
        if method == "GET":
            repo = url.removeprefix("https://api.github.com/repos/").removesuffix("/installation")
            data = {"id": self.installations[repo], "app_id": 123, "suspended_at": None}
            return 200, {}, json.dumps(data).encode()
        data = {
            "token": "fixture-installation-token-" + str(len(self.calls)),
            "expires_at": dt.datetime.fromtimestamp(self.expiry, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "permissions": self.permissions,
        }
        return 201, {}, json.dumps(data).encode()

    def app(self):
        return collector.GitHubApp(self.app_config, self.sources, self.pem)

    def test_jwt_is_rs256_and_short_lived(self):
        app = self.app()
        with patch.object(collector.time, "time", return_value=NOW):
            token = app.jwt()
        head, body, signature = token.split(".")
        self.assertEqual(json.loads(decode(head))["alg"], "RS256")
        claims = json.loads(decode(body))
        self.assertEqual(claims, {"iat": NOW - 60, "exp": NOW + 540, "iss": "123"})
        self.key.public_key().verify(decode(signature), (head + "." + body).encode(), padding.PKCS1v15(), hashes.SHA256())

    def test_two_orgs_use_distinct_repository_scoped_tokens(self):
        app = self.app()
        with patch.object(collector.time, "time", return_value=NOW):
            first = app.token("Scetrov/efctl", self.response)
            second = app.token("AnotherOrg/project", self.response)
        self.assertNotEqual(first, second)
        posts = [c for c in self.calls if c[2] == "POST"]
        self.assertEqual([p[0] for p in posts], [
            "https://api.github.com/app/installations/111/access_tokens",
            "https://api.github.com/app/installations/222/access_tokens",
        ])
        self.assertEqual([json.loads(p[3]) for p in posts], [
            {"repository_ids": [SOURCE["repositoryId"]], "permissions": {"actions": "read"}},
            {"repository_ids": [42], "permissions": {"actions": "read"}},
        ])
        for _, headers, _, _ in self.calls:
            self.assertTrue(headers["Authorization"].startswith("Bearer "))

    def test_cache_is_memory_only_and_refreshes_before_expiry(self):
        app = self.app()
        with patch.object(collector.time, "time", return_value=NOW):
            first = app.token("Scetrov/efctl", self.response)
            self.assertEqual(app.token("scetrov/EFCTL", self.response), first)
        self.assertEqual(len(self.calls), 2)
        self.expiry = NOW + 7200
        with patch.object(collector.time, "time", return_value=NOW + 3550):
            self.assertNotEqual(app.token("Scetrov/efctl", self.response), first)
        self.assertEqual(len([c for c in self.calls if c[2] == "POST"]), 2)

    def test_unknown_repo_and_installation_fail_closed(self):
        app = self.app()
        request = Mock(side_effect=self.response)
        with self.assertRaises(collector.Failure):
            app.token("Unapproved/repo", request)
        request.assert_not_called()
        self.installations["Scetrov/efctl"] = 999
        with patch.object(collector.time, "time", return_value=NOW), self.assertRaises(collector.Failure):
            app.token("Scetrov/efctl", request)
        self.assertFalse(any(c[2] == "POST" for c in self.calls))

    def test_suspended_or_different_app_installation_rejected(self):
        for change in [{"suspended_at": "2026-10-01T00:00:00Z"}, {"app_id": 999}]:
            with self.subTest(change=change):
                request = Mock(return_value=(200, {}, json.dumps({"id": 111, "app_id": 123, **change}).encode()))
                with patch.object(collector.time, "time", return_value=NOW), self.assertRaises(collector.Failure):
                    self.app().token("Scetrov/efctl", request)
                self.assertEqual(request.call_count, 1)

    def test_expired_or_overprivileged_token_rejected(self):
        for permissions, expiry in [
            ({"actions": "write"}, NOW + 3600),
            ({"actions": "read", "contents": "read"}, NOW + 3600),
            ({"metadata": "read"}, NOW + 3600),
            ({"actions": "read"}, NOW - 1),
        ]:
            with self.subTest(permissions=permissions, expiry=expiry):
                self.permissions, self.expiry = permissions, expiry
                with patch.object(collector.time, "time", return_value=NOW), self.assertRaises(collector.Failure):
                    self.app().token("Scetrov/efctl", self.response)

    def test_bad_key_and_invalid_installation_configuration_rejected(self):
        with self.assertRaises(collector.Failure):
            collector.GitHubApp(self.app_config, self.sources, b"not a key")
        for field, value in [("appId", 0), ("installationIds", []), ("installationIds", [111, 111]), ("installationIds", ["111"]), ("installationIds", [0])]:
            with self.subTest(field=field, value=value), self.assertRaises(collector.Failure):
                collector.GitHubApp({**self.app_config, field: value}, self.sources, self.pem)

    def test_bad_token_response_and_http_failures_are_redacted(self):
        for response in [(302, {"Location": "https://attacker.invalid"}, b"secret-body"),
                         (200, {}, b"not-json")]:
            with self.subTest(response=response[0]):
                with patch.object(collector.time, "time", return_value=NOW), self.assertRaises(collector.Failure) as error:
                    self.app().token("Scetrov/efctl", Mock(return_value=response))
                self.assertNotIn("secret", str(error.exception))
        app = self.app()
        with patch.object(collector.time, "time", return_value=NOW), self.assertRaisesRegex(collector.Failure, "^http_403$"):
            app.token("Scetrov/efctl", Mock(side_effect=collector.Failure("http_403")))
        self.assertFalse(app.cache)

    def test_app_requests_never_follow_returned_endpoint_urls(self):
        def request(url, headers, limit, method="GET", body=None):
            if method == "GET":
                return 200, {}, json.dumps({"id": 111, "app_id": 123, "suspended_at": None,
                                           "access_tokens_url": "https://attacker.invalid/steal"}).encode()
            self.assertEqual(url, "https://api.github.com/app/installations/111/access_tokens")
            return self.response(url, headers, limit, method, body)
        with patch.object(collector.time, "time", return_value=NOW):
            self.app().token("Scetrov/efctl", request)

    def test_transport_uses_installation_token_not_app_jwt_for_actions(self):
        auth = self.app()
        http = collector.Http(auth, "dtrack-fixture-key", "https://dtrack.example")
        def request(url, headers, limit, method="GET", body=None):
            if "/actions/" in url:
                self.assertTrue(headers["Authorization"].startswith("Bearer fixture-installation-token-"))
                return 200, {}, b'{"workflow_runs":[]}'
            return self.response(url, headers, limit, method, body)
        with patch.object(collector.time, "time", return_value=NOW), patch.object(http, "request", side_effect=request):
            http.github("/repos/Scetrov/efctl/actions/runs")


if __name__ == "__main__":
    unittest.main()
