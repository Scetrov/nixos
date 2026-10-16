"""Rootless Podman regression fixture for the production Hermes Caddy rules.

Run explicitly: python3 scripts/tests/test_hermes_auth_expiry.py
Only a random localhost port is published; no real auth credentials are used.
"""

import http.client
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "src/roles/nixos/files/etc/nixos/modules"


def production_rules():
    source = (MODULES / "caddy.nix").read_text()
    site = source.split('virtualHosts."hermes.net.scetrov.live"', 1)[1].split(
        'virtualHosts."homeassistant.net.scetrov.live"', 1
    )[0]
    if "builtins.readFile ./hermes-auth.caddy" in site:
        return (MODULES / "hermes-auth.caddy").read_text()
    return site.split("extraConfig = ''", 1)[1].split("'';", 1)[0]


@unittest.skipUnless(__name__ == "__main__", "Run the Podman fixture explicitly as a script")
class HermesAuthExpiryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        image = re.search(
            r'default = "(docker.io/library/caddy:[^"]+)"',
            (MODULES / "hermes.nix").read_text(),
        ).group(1)
        cls.name = "hermes-auth-test-" + uuid.uuid4().hex[:12]
        cls.directory = tempfile.TemporaryDirectory(prefix="hermes-auth-")
        cls.addClassCleanup(cls.directory.cleanup)
        cls.addClassCleanup(
            subprocess.run,
            ["podman", "rm", "--force", cls.name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        config = Path(cls.directory.name) / "Caddyfile"
        config.write_text(
            "{\n admin off\n auto_https off\n}\n:8080 {\n"
            + production_rules()
            + "\n}\n"
            + """
:9000 {
    @valid {
        header Cookie fixture=valid
        method GET
        path /outpost.goauthentik.io/auth/caddy
    }
    handle @valid {
        header X-Authentik-Username fixture-user
        respond 204
    }
    @unauthorized header X-Fixture-Status 401
    respond @unauthorized "Unauthorized" 401
    @denied header X-Fixture-Status 403
    respond @denied "Forbidden" 403
    @failed header X-Fixture-Status 500
    respond @failed "Unavailable" 500
    header Location https://identity.invalid/authorize
    @see_other header X-Fixture-Status 303
    respond @see_other 303
    @temporary header X-Fixture-Status 307
    respond @temporary 307
    @permanent header X-Fixture-Status 308
    respond @permanent 308
    respond 302
}
:8787 {
    respond "{http.request.method}|{http.request.uri}|{http.request.header.X-Authentik-Username}" 200
}
"""
        )
        result = subprocess.run(
            [
                "podman", "run", "--detach", "--name", cls.name,
                "--publish", "127.0.0.1::8080",
                "--volume", f"{config}:/etc/caddy/Caddyfile:ro",
                image,
            ],
            capture_output=True, text=True, check=True,
        )
        if not result.stdout.strip():
            raise RuntimeError("Podman did not return a container ID")
        port = subprocess.check_output(
            ["podman", "port", cls.name, "8080/tcp"], text=True
        ).strip()
        cls.port = int(port.rsplit(":", 1)[1])
        for _ in range(50):
            try:
                cls.request("/")
                break
            except (OSError, http.client.HTTPException):
                time.sleep(0.1)
        else:
            raise RuntimeError("Caddy fixture did not become ready")

    @classmethod
    def request(cls, path, headers=None, method="GET", body=None):
        connection = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read().decode()
        finally:
            connection.close()

    def test_expired_background_requests_never_redirect(self):
        for path in [
            "/api", "/api/", "/api/projects", "/api/settings",
            "/api/crons/recent", "/api/sessions/events?session=x",
            "/health", "/health/ready",
        ]:
            with self.subTest(path=path):
                status, headers, body = self.request(path)
                self.assertEqual(status, 401)
                self.assertNotIn("Location", headers)
                self.assertEqual(headers.get("Content-Type"), "application/json")
                self.assertEqual(headers.get("Cache-Control"), "no-store")
                self.assertEqual(json.loads(body), {"error": "unauthorized"})

    def test_other_auth_redirect_statuses_become_401(self):
        for upstream_status in [303, 307, 308]:
            with self.subTest(status=upstream_status):
                status, headers, _ = self.request(
                    "/api/projects", {"X-Fixture-Status": str(upstream_status)}
                )
                self.assertEqual(status, 401)
                self.assertNotIn("Location", headers)

    def test_browser_navigation_keeps_auth_redirect(self):
        for path in ["/", "/login?next=%2F", "/static/ui.js", "/api-not-a-route"]:
            with self.subTest(path=path):
                status, headers, _ = self.request(path)
                self.assertEqual(status, 302)
                self.assertEqual(headers.get("Location"), "https://identity.invalid/authorize")

    def test_authenticated_requests_preserve_method_uri_and_identity(self):
        for path in ["/api/projects?q=one", "/health", "/"]:
            with self.subTest(path=path):
                status, _, body = self.request(
                    path, {"Cookie": "fixture=valid"}, method="POST", body="original-body"
                )
                self.assertEqual(status, 200)
                self.assertEqual(body, f"POST|{path}|fixture-user")

    def test_auth_failures_stay_denied(self):
        for expected in [401, 403, 500]:
            for path in ["/api/projects", "/health", "/"]:
                with self.subTest(status=expected, path=path):
                    status, _, body = self.request(
                        path, {"X-Fixture-Status": str(expected)}
                    )
                    self.assertEqual(status, expected)
                    self.assertNotIn("fixture-user", body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
