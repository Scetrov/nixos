"""Disposable native Forgejo/OIDC/Caddy browser acceptance; no production state.

FORGEJO_TEST_BINARY and CADDY_BIN enable the fixture. Run with a Python containing
playwright and cryptography, and CHROMIUM_BIN pointing to a browser executable.
"""
import base64
import hashlib
import http.server
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.parse

from scripts.tests.test_forgejo_private_proxy import free_port
from scripts.tests.test_forgejo_reconcile import reconcile

ROOT = Path(__file__).resolve().parents[2]
FORGEJO = os.environ.get("FORGEJO_TEST_BINARY")
CADDY = os.environ.get("CADDY_BIN")
CHROMIUM = os.environ.get("CHROMIUM_BIN")


def b64(value):
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


class IdentityProvider(http.server.BaseHTTPRequestHandler):
    """Test-only issuer with real signatures, state round-trip and PKCE checks."""

    def log_message(self, *_args):
        pass

    def send(self, status, body=b"", **headers):
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key.replace("_", "-"), value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(url.query)
        issuer = self.server.issuer
        if url.path == "/.well-known/openid-configuration":
            self.send(200, json.dumps({
                "issuer": issuer, "authorization_endpoint": issuer + "/authorize",
                "token_endpoint": issuer + "/token", "jwks_uri": issuer + "/jwks",
                "userinfo_endpoint": issuer + "/userinfo",
                "id_token_signing_alg_values_supported": ["RS256"],
                "response_types_supported": ["code"], "subject_types_supported": ["public"],
            }).encode(), Content_Type="application/json")
        elif url.path == "/jwks":
            self.send(200, json.dumps({"keys": [self.server.jwk]}).encode(),
                      Content_Type="application/json")
        elif url.path == "/userinfo":
            self.send(200, json.dumps(self.server.claims()).encode(), Content_Type="application/json")
        elif url.path == "/authorize":
            if self.server.mode == "outage":
                self.send(503, b"Fixture provider unavailable")
            elif "fixture_idp=1" not in self.headers.get("Cookie", "") and "continue" not in query:
                self.send(200, ('<a href="' + self.path + '&continue=1">Fixture sign in</a>').encode(),
                          Content_Type="text/html")
            else:
                self.server.authorization = query
                result = {"state": query["state"][0]}
                result.update({"error": "access_denied"} if self.server.mode == "denied"
                              else {"code": "fixture-code"})
                self.send(302, Location=query["redirect_uri"][0] + "?" + urllib.parse.urlencode(result),
                          Set_Cookie="fixture_idp=1; Path=/; HttpOnly; SameSite=Lax")
        else:
            self.send(404)

    def do_POST(self):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        query = urllib.parse.parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
        expected = self.server.authorization["code_challenge"][0]
        if b64(hashlib.sha256(query.get("code_verifier", [""])[0].encode()).digest()) != expected:
            self.send(400)
            return
        claims = self.server.claims()
        claims.update(iss=self.server.issuer, aud="fixture-client", iat=int(time.time()),
                      exp=int(time.time()) + 300)
        if "nonce" in self.server.authorization:
            claims["nonce"] = self.server.authorization["nonce"][0]
        payload = b64(json.dumps({"alg": "RS256", "kid": "fixture"}).encode()) + "." + b64(json.dumps(claims).encode())
        signature = self.server.key.sign(payload.encode(), padding.PKCS1v15(), hashes.SHA256())
        self.send(200, json.dumps({"access_token": "fixture-access", "token_type": "Bearer",
                                  "expires_in": 300, "id_token": payload + "." + b64(signature)}).encode(),
                  Content_Type="application/json")


class DeploymentScopeTests(unittest.TestCase):
    def test_forgejo_only_skips_unrelated_operations(self):
        import yaml

        role = ROOT / "src/roles/nixos"
        defaults = yaml.safe_load((role / "defaults/main.yml").read_text())
        self.assertIn("'forgejo' in ansible_run_tags", defaults["nixos_forgejo_only"])
        tasks = yaml.safe_load((role / "tasks/main.yml").read_text())
        for task in tasks:
            if task.get("ansible.builtin.include_tasks") in (
                    "channel.yml", "headscale-enrolment.yml", "garage-provisioning.yml", "podman.yml"):
                self.assertIn("not (nixos_forgejo_only | bool)", task["when"])
        tasks = yaml.safe_load((role / "tasks/rebuild.yml").read_text())
        for task in tasks:
            if "Frontier Indexer" in task.get("name", ""):
                self.assertTrue(any("not (nixos_forgejo_only | bool)" in condition
                                    for condition in task["when"]))


@unittest.skipUnless(FORGEJO and CADDY and CHROMIUM, "Set native fixture binary paths")
class AutomaticSSOTests(unittest.TestCase):
    def test_browser_and_protocol_boundaries(self):
        from cryptography.hazmat.primitives.asymmetric import rsa
        from playwright.sync_api import sync_playwright

        with tempfile.TemporaryDirectory(prefix="forgejo-sso-") as directory:
            root = Path(directory)
            provider = http.server.ThreadingHTTPServer(("127.0.0.1", 0), IdentityProvider)
            provider.issuer = f"http://127.0.0.1:{provider.server_port}"
            provider.mode = "normal"
            provider.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            numbers = provider.key.public_key().public_numbers()
            provider.jwk = {"kty": "RSA", "kid": "fixture", "use": "sig", "alg": "RS256",
                            "n": b64(numbers.n.to_bytes(256, "big")),
                            "e": b64(numbers.e.to_bytes(3, "big"))}
            provider.claims = lambda: {"sub": "fixture-owner", "preferred_username": "sso-owner",
                                      "nickname": "sso-owner", "name": "Fixture Owner",
                                      "email": "sso@example.invalid", "email_verified": True,
                                      "groups": [] if provider.mode == "ungrouped" else ["Forgejo Owners"]}
            thread = threading.Thread(target=provider.serve_forever, daemon=True)
            thread.start()
            processes = []
            try:
                backend_port, proxy_port, ssh_port = free_port(), free_port(), free_port()
                base = f"http://127.0.0.1:{proxy_port}"
                config = root / "app.ini"
                config.write_text(f"""[database]
DB_TYPE = sqlite3
PATH = {root}/forgejo.db
[security]
INSTALL_LOCK = true
[server]
APP_DATA_PATH = {root}/data
HTTP_ADDR = 127.0.0.1
HTTP_PORT = {backend_port}
ROOT_URL = {base}/
LANDING_PAGE = login
START_SSH_SERVER = true
SSH_LISTEN_HOST = 127.0.0.1
SSH_LISTEN_PORT = {ssh_port}
SSH_PORT = {ssh_port}
SSH_USER = git
BUILTIN_SSH_SERVER_USER = git
SSH_SERVER_HOST_KEYS = {root}/data/ssh/forgejo.rsa
[repository]
ROOT = {root}/repositories
FORCE_PRIVATE = true
[service]
DISABLE_REGISTRATION = true
REQUIRE_SIGNIN_VIEW = true
ENABLE_INTERNAL_SIGNIN = false
ENABLE_BASIC_AUTHENTICATION = false
[oauth2_client]
ENABLE_AUTO_REGISTRATION = true
USERNAME = nickname
ACCOUNT_LINKING = disabled
REGISTER_EMAIL_CONFIRM = false
[log]
MODE = console
LEVEL = Error
""")
                cli = [FORGEJO, "--config", str(config), "--work-path", directory]

                def command(*args):
                    result = subprocess.run([*cli, *args], capture_output=True, text=True, timeout=60)
                    self.assertEqual(result.returncode, 0, "Fixture CLI failed; diagnostics suppressed")
                    return result.stdout

                command("migrate")
                (root / "client-id").write_text("fixture-client")
                (root / "client-secret").write_text("fixture-client-secret")
                reconcile.reconcile(FORGEJO, str(config), directory, root / "client-id",
                                    root / "client-secret", provider.issuer + "/.well-known/openid-configuration")
                evaluated = json.loads(subprocess.check_output([
                    "nix-instantiate", "--eval", "--strict", "--json", "--expr",
                    "import ./src/roles/nixos/tests/forgejo-eval.nix {}"], cwd=ROOT, text=True))
                route = evaluated["caddyConfig"].replace("127.0.0.1:3002", f"127.0.0.1:{backend_port}")
                # Fixture-only HTTP/loopback exceptions; production remains HTTPS/private.
                route = route.replace("not remote_ip ", "not remote_ip 127.0.0.1/32 ").replace("; Secure", "")
                caddyfile = root / "Caddyfile"
                caddyfile.write_text("{\n admin off\n auto_https off\n}\n" + base + " {\n" + route + "\n}\n")
                log = self.enterContext(open(root / "services.log", "w"))
                for args in [[*cli, "web"], [CADDY, "run", "--config", str(caddyfile), "--adapter", "caddyfile"]]:
                    processes.append(subprocess.Popen(args, stdout=log, stderr=log))
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(executable_path=CHROMIUM, headless=True)
                    try:
                        context = browser.new_context()
                        page = context.new_page()
                        for _ in range(100):
                            try:
                                if context.request.get(base + "/api/healthz").status == 200:
                                    break
                            except Exception:
                                pass
                            self.assertTrue(all(p.poll() is None for p in processes), "Fixture process exited")
                            time.sleep(0.1)
                        else:
                            self.fail("Fixture readiness timed out")

                        # Reproduce native current behavior without Caddy's browser redirect.
                        native = context.request.get(f"http://127.0.0.1:{backend_port}/user/login")
                        self.assertEqual(native.status, 200)
                        self.assertIn("/user/oauth2/authentik", native.text())
                        # Direct fresh visit enters the IdP, absent IdP session prompts there.
                        page.goto(base + "/")
                        self.assertTrue(page.url.startswith(provider.issuer + "/authorize"))
                        page.get_by_text("Fixture sign in", exact=True).click()
                        page.wait_for_url(base + "/")
                        self.assertNotIn("/user/login", page.url)
                        # Existing Forgejo session does not start another authorization.
                        provider.mode = "outage"
                        page.goto(base + "/")
                        self.assertEqual(page.url, base + "/")
                        # Explicit login retains native SSO remember-me behavior (303),
                        # rather than the proxy's 302 auto-entry response.
                        response = context.request.get(base + "/user/login", headers={
                            "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"}, max_redirects=0)
                        self.assertEqual(response.status, 303)
                        self.assertIn("prompt=none", response.headers["location"])
                        provider.mode = "normal"
                        token = command("admin", "user", "generate-access-token", "--username", "sso-owner",
                                        "--token-name", "fixture", "--scopes", "all", "--raw").strip().splitlines()[-1]
                        auth = {"Authorization": "token " + token}
                        response = context.request.post(base + "/api/v1/user/repos", headers=auth,
                                                        data={"name": "deep-link", "private": True, "auto_init": True})
                        self.assertEqual(response.status, 201)
                        # Logout uses real CSRF protection and must stop on the manual page.
                        page.goto(base + "/")
                        page.locator('a[data-url="/user/logout"]').first.evaluate("element => element.click()")
                        page.wait_for_timeout(500)
                        self.assertEqual(page.url, base + "/user/login")
                        self.assertIn("/user/oauth2/authentik", page.content())
                        page.locator('a[href="/user/oauth2/authentik"]').click()
                        page.wait_for_url(base + "/")
                        self.assertFalse(any(c["name"] == "forgejo_sso_pause" and c["value"] for c in context.cookies()))

                        # A second logout still lands manually, but a later visit must
                        # resume SSO rather than retaining the pause for the browser session.
                        page.locator('a[data-url="/user/logout"]').first.evaluate("element => element.click()")
                        page.wait_for_timeout(500)
                        self.assertEqual(page.url, base + "/user/login")
                        page.goto(base + "/")
                        self.assertEqual(page.url, base + "/", "A prior logout still blocks automatic SSO")

                        # Remove only Forgejo's session; retain the IdP session for seamless SSO.
                        def expire_session():
                            cookies = context.cookies()
                            context.clear_cookies()
                            context.add_cookies([c for c in cookies if c["name"] == "fixture_idp"])

                        expire_session()
                        page.goto(base + "/sso-owner/deep-link/src/branch/main/README.md")
                        self.assertEqual(page.url, base + "/sso-owner/deep-link/src/branch/main/README.md")
                        self.assertEqual(page.locator("title").count(), 1)
                        # Explicit destination queries remain native, including unsafe URLs.
                        expire_session()
                        page.goto(base + "/user/login?redirect_to=https%3A%2F%2Fexample.invalid%2F")
                        self.assertTrue(page.url.startswith(base + "/"))
                        self.assertNotIn("example.invalid", page.url)
                        # Missing access-group claims cannot establish a Forgejo session.
                        expire_session()
                        provider.mode = "ungrouped"
                        page.goto(base + "/")
                        self.assertIn(context.request.get(base + "/api/v1/user").status, (401, 403))
                        # Access denial and invalid callbacks terminate on native error responses.
                        expire_session()
                        provider.mode = "denied"
                        page.goto(base + "/")
                        self.assertEqual(page.url, base + "/user/login")
                        self.assertIn("/user/oauth2/authentik", page.content())
                        invalid = page.goto(base + "/user/oauth2/authentik/callback?state=invalid&code=invalid")
                        self.assertGreaterEqual(invalid.status, 400)
                        provider.mode = "outage"
                        expire_session()
                        page.goto(base + "/")
                        self.assertEqual(page.locator("body").inner_text(), "Fixture provider unavailable")
                        provider.mode = "normal"
                        # Machine requests never receive this browser-only proxy redirect.
                        for path in ["/user/login", "/api/healthz", "/api/v1/version",
                                     "/sso-owner/deep-link.git/info/refs?service=git-upload-pack"]:
                            response = context.request.get(base + path, max_redirects=0)
                            self.assertNotIn("/user/oauth2/", response.headers.get("location", ""))
                        response = context.request.get(base + "/api/v1/user", headers=auth)
                        self.assertEqual(response.status, 200)
                        # Real native Git transports with service credentials, no browser headers.
                        git_env = os.environ.copy()
                        git_env.update(GIT_TERMINAL_PROMPT="0", GIT_CONFIG_COUNT="1",
                                       GIT_CONFIG_KEY_0="http.extraHeader", GIT_CONFIG_VALUE_0="Authorization: Bearer " + token)
                        result = subprocess.run(["git", "ls-remote", base + "/sso-owner/deep-link.git"],
                                                env=git_env, capture_output=True, timeout=15)
                        self.assertEqual(result.returncode, 0, "Native Git HTTPS token access failed")
                        key = root / "fixture-key"
                        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
                        response = context.request.post(base + "/api/v1/user/keys", headers=auth,
                            data={"title": "fixture", "key": key.with_suffix(".pub").read_text()})
                        self.assertEqual(response.status, 201)
                        git_env = os.environ.copy()
                        git_env["GIT_SSH_COMMAND"] = (f"ssh -i {key} -o IdentitiesOnly=yes -o BatchMode=yes "
                            f"-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile={root}/known_hosts")
                        result = subprocess.run(["git", "ls-remote",
                            f"ssh://git@127.0.0.1:{ssh_port}/sso-owner/deep-link.git"],
                            env=git_env, capture_output=True, timeout=15)
                        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
                        # Host-side recovery remains usable even with the provider unavailable.
                        provider.mode = "outage"
                        self.assertIn("authentik", command("admin", "auth", "list"))
                        provider.mode = "normal"
                        response = context.request.post(base + "/api/v1/repos/sso-owner/deep-link/hooks", headers=auth,
                            data={"type": "gitea", "config": {"url": "http://127.0.0.1:9/hook", "content_type": "json"},
                                  "events": ["push"], "active": False})
                        self.assertEqual(response.status, 201)
                        response = context.request.get(base + "/user/login?sso=manual",
                            headers={"Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"}, max_redirects=0)
                        self.assertEqual(response.status, 200)
                    finally:
                        browser.close()
            finally:
                for process in reversed(processes):
                    process.terminate()
                    process.wait(timeout=15)
                provider.shutdown()
                provider.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
