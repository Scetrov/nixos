"""Exercise the evaluated Forgejo route with a real Caddy binary, no TLS secrets.

Run with CADDY_BIN=/path/to/caddy python3 -m unittest \
    scripts.tests.test_forgejo_private_proxy -v
Only the fixture adds loopback to the private list to exercise admitted requests.
The unmodified source matcher must deny loopback, even with spoofed headers.
"""
import http.server
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
CADDY = os.environ.get("CADDY_BIN") or shutil.which("caddy")


class Backend(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"fixture-backend")

    def log_message(self, *_args):
        pass


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@unittest.skipUnless(CADDY, "Set CADDY_BIN to run real proxy tests")
class PrivateProxyTests(unittest.TestCase):
    def test_source_and_internal_route_boundaries(self):
        evaluated = json.loads(subprocess.check_output([
            "nix-instantiate", "--eval", "--strict", "--json", "--expr",
            "import ./src/roles/nixos/tests/forgejo-eval.nix {}",
        ], cwd=ROOT, text=True))
        self.assertTrue(evaluated["passed"])
        backend = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Backend)
        thread = threading.Thread(target=backend.serve_forever, daemon=True)
        thread.start()
        try:
            for allow_fixture_peer in (False, True):
                route = evaluated["caddyConfig"].replace(
                    "127.0.0.1:3002", f"127.0.0.1:{backend.server_port}")
                if allow_fixture_peer:
                    route = route.replace("not remote_ip ", "not remote_ip 127.0.0.1/32 ")
                port = free_port()
                with tempfile.TemporaryDirectory() as temp:
                    path = Path(temp) / "Caddyfile"
                    path.write_text("{\n admin off\n auto_https off\n}\n"
                                    + f"http://127.0.0.1:{port} {{\n{route}\n}}\n")
                    subprocess.run([CADDY, "validate", "--config", str(path),
                                    "--adapter", "caddyfile"], check=True,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    with open(Path(temp) / "caddy.log", "w+") as log:
                        process = subprocess.Popen([CADDY, "run", "--config", str(path),
                                                    "--adapter", "caddyfile"], stdout=log, stderr=log)
                        try:
                            for _ in range(100):
                                if process.poll() is not None:
                                    self.fail("Fixture Caddy exited before becoming ready")
                                try:
                                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                                        break
                                except OSError:
                                    time.sleep(0.05)
                            else:
                                self.fail("Fixture Caddy readiness timed out")
                            for endpoint in ("/", "/api/v1/version", "/metrics", "/metrics/test",
                                             "/api/internal", "/api/internal/test"):
                                request = urllib.request.Request(
                                    f"http://127.0.0.1:{port}{endpoint}", headers={
                                        "X-Forwarded-For": "10.229.5.18",
                                        "X-Real-IP": "100.64.0.3",
                                    })
                                try:
                                    with urllib.request.urlopen(request, timeout=2) as response:
                                        status = response.status
                                except urllib.error.HTTPError as response:
                                    status = response.code
                                    response.close()
                                expected = (404 if endpoint.startswith(("/metrics", "/api/internal"))
                                            else 200) if allow_fixture_peer else 403
                                with self.subTest(admitted=allow_fixture_peer, path=endpoint):
                                    self.assertEqual(status, expected)
                        finally:
                            process.terminate()
                            process.wait(timeout=10)
        finally:
            backend.shutdown()
            backend.server_close()
            thread.join(timeout=5)
