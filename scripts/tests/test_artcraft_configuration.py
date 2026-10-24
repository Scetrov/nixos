"""Static contract checks plus real Caddy tests against a disposable auth stub."""

import hashlib
import http.client
import http.server
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest


REPO = Path(__file__).resolve().parents[2]
MODULES = REPO / "src/roles/nixos/files/etc/nixos/modules"
INVENTORY = (REPO / "config/artcraft.yml").read_text()
SLUGS = re.findall(r"^  - slug: (.+)$", INVENTORY, re.M)


class ConfigurationTests(unittest.TestCase):
    def test_routes_icons_and_identity_match_inventory(self):
        self.assertEqual(len(SLUGS), 13)
        route = (MODULES / "artcraft.caddy").read_text()
        branding = (REPO / "src/roles/nixos/tasks/branding.yml").read_text()
        for block in INVENTORY.split("  - slug: ")[1:]:
            slug = block.splitlines()[0]
            digest = re.search(r"^    icon_sha256: (.+)$", block, re.M)[1]
            filename = f"{slug}-{digest[:12]}.png"
            icon = REPO / "src/roles/nixos/files/etc/nixos/branding" / filename
            self.assertEqual(hashlib.sha256(icon.read_bytes()).hexdigest(), digest)
            self.assertIn(filename, branding)
            self.assertIn(f"handle_path /{slug}/*", route)
            self.assertIn(f"redir /{slug} /{slug}/ 308", route)
        identity = (REPO / "terraform/artcraft.tf").read_text()
        self.assertIn('yamldecode(file("${path.module}/../config/artcraft.yml"))', identity)
        self.assertEqual(identity.count("group   = authentik_group.all_applications.id"), 2)
        self.assertIn('meta_hide          = true', identity)
        tiles = identity.split('resource "authentik_application" "artcraft_editor"')[1].split('\nresource ')[0]
        self.assertNotIn("protocol_provider", tiles)
        self.assertIn('https://artcraft.net.scetrov.live/${each.key}/', tiles)
        self.assertIn('substr(each.value.icon_sha256, 0, 12)', tiles)
        self.assertIn("authentik_provider_proxy.artcraft.id,", (REPO / "terraform/authentik.tf").read_text())
        self.assertIn('"artcraft.net.scetrov.live"', (MODULES / "local-networking.nix").read_text())
        caddy = (MODULES / "caddy.nix").read_text().split('virtualHosts."artcraft.net.scetrov.live"')[1].split('virtualHosts.')[0]
        self.assertIn('useACMEHost = "scetrov.live"', caddy)
        self.assertIn("output stderr", caddy)

    def test_targeted_deployment_does_not_rebuild_sources_or_refresh_secrets(self):
        deploy = (REPO / "src/artcraft-deploy.yml").read_text()
        self.assertIn("ansible_limit | default('') == 'habiki'", deploy)
        self.assertIn("-target=authentik_policy_binding.artcraft_editor_access", deploy)
        self.assertIn("-target=authentik_outpost.proxy", deploy)
        self.assertNotIn("--refresh-generated-secrets", deploy)
        self.assertNotIn("role: secrets", deploy)
        self.assertNotIn("channel", deploy.split("tasks:")[-1].replace("without updating channels", ""))
        for path in (REPO / "src/roles/artcraft/tasks").glob("*.yml"):
            self.assertNotRegex(path.read_text(), r"\b(podman|cargo|rustup|trunk)\b")


class AuthStub(http.server.BaseHTTPRequestHandler):
    unavailable = False

    def do_GET(self):
        if self.path != "/outpost.goauthentik.io/auth/caddy":
            status = 200
        elif self.unavailable:
            status = 503
        elif self.headers.get("Authorization") == "Bearer allowed":
            status = 200
        elif self.headers.get("Authorization"):
            status = 403
        else:
            status = 302
        self.send_response(status)
        if status == 302:
            self.send_header("Location", "https://identity.invalid/login")
        self.end_headers()
        self.wfile.write(b"auth-stub")

    def log_message(self, *args):
        pass


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class CaddyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        binary = os.environ.get("ARTCRAFT_CADDY") or shutil.which("caddy")
        if not binary:
            raise unittest.SkipTest("Set ARTCRAFT_CADDY to run real Caddy auth/file regression checks")
        cls.temp = tempfile.TemporaryDirectory(prefix="artcraft-caddy-test-")
        cls.addClassCleanup(cls.temp.cleanup)
        root = Path(cls.temp.name)
        cls.auth = http.server.ThreadingHTTPServer(("127.0.0.1", 0), AuthStub)
        cls.addClassCleanup(cls.auth.server_close)
        cls.addClassCleanup(cls.auth.shutdown)
        threading.Thread(target=cls.auth.serve_forever, daemon=True).start()
        cls.port = free_port()
        for slug in SLUGS:
            site = root / "site" / slug
            site.mkdir(parents=True)
            (site / "index.html").write_text("<h1>" + slug + "</h1>")
            (site / "app.js").write_text("// checked runtime")
            (site / "app-0123456789abcdef.js").write_text("// hashed runtime")
            (site / "app.wasm").write_bytes(b"\0asm\x01\0\0\0")
            (site / "font.ttf").write_bytes(b"font")
        route = (MODULES / "artcraft.caddy").read_text().replace(
            "127.0.0.1:9000", f"127.0.0.1:{cls.auth.server_port}"
        ).replace("/var/lib/artcraft", str(root / "site"))
        config = root / "Caddyfile"
        config.write_text("{\nadmin off\nauto_https off\n}\n" + f"http://127.0.0.1:{cls.port} {{\n{route}\n}}\n")
        cls.log = (root / "caddy.log").open("w+")
        cls.addClassCleanup(cls.log.close)
        cls.process = subprocess.Popen([binary, "run", "--config", str(config), "--adapter", "caddyfile"],
                                       stdout=cls.log, stderr=cls.log)
        cls.addClassCleanup(cls.stop)
        for _ in range(100):
            if cls.process.poll() is not None:
                cls.log.seek(0)
                raise RuntimeError("Caddy failed: " + cls.log.read())
            try:
                cls.request("/outpost.goauthentik.io/ping", allowed=False)
                break
            except OSError:
                time.sleep(0.05)
        else:
            raise RuntimeError("Caddy did not become ready")

    @classmethod
    def stop(cls):
        cls.process.terminate()
        cls.process.wait(timeout=10)

    @classmethod
    def request(cls, path, allowed=True, token=None):
        headers = {"Authorization": "Bearer allowed"} if allowed else {}
        if token:
            headers["Authorization"] = token
        conn = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=10)
        try:
            conn.request("GET", path, headers=headers)
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def test_all_routes_redirect_and_serve_only_after_auth(self):
        for slug in SLUGS:
            with self.subTest(slug=slug):
                status, headers, body = self.request("/" + slug)
                self.assertEqual(status, 308)
                self.assertEqual(headers["Location"], "/" + slug + "/")
                status, headers, body = self.request("/" + slug + "/")
                self.assertEqual(status, 200)
                self.assertIn(slug.encode(), body)
                self.assertEqual(headers["Cache-Control"], "private, no-cache")
                for suffix in ("", "/", "/app.js", "/app.wasm", "/font.ttf"):
                    status, headers, body = self.request("/" + slug + suffix, allowed=False)
                    self.assertEqual(status, 302)
                    self.assertEqual(headers["Cache-Control"], "no-store")
                    self.assertNotIn(b"checked runtime", body)
                    status, headers, body = self.request("/" + slug + suffix, token="Bearer denied")
                    self.assertEqual(status, 403)
        self.assertEqual(self.request("/")[1]["Location"], "/photocraft/")
        self.assertEqual(self.request("/", allowed=False)[0], 302)

    def test_callback_bypasses_auth_but_outpost_failure_is_closed(self):
        self.assertEqual(self.request("/outpost.goauthentik.io/callback", allowed=False)[0], 200)
        AuthStub.unavailable = True
        try:
            for path in ("/photocraft/", "/photocraft/app.js", "/photocraft/app.wasm"):
                status, headers, body = self.request(path)
                self.assertEqual(status, 503)
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertNotIn(b"checked runtime", body)
        finally:
            AuthStub.unavailable = False

    def test_missing_paths_mime_and_cache(self):
        for path in ("/missing/", "/versions/", "/photocraft/missing.js", "/photocraft/no-directory/"):
            self.assertEqual(self.request(path)[0], 404)
        status, headers, body = self.request("/photocraft/app.wasm")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/wasm")
        self.assertEqual(headers["Cache-Control"], "private, no-cache")
        self.assertTrue(body.startswith(b"\0asm"))
        self.assertEqual(self.request("/photocraft/font.ttf")[1]["Content-Type"], "font/ttf")
        self.assertEqual(self.request("/photocraft/app-0123456789abcdef.js")[1]["Cache-Control"],
                         "private, max-age=31536000, immutable")


if __name__ == "__main__":
    unittest.main()
