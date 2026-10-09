"""Exercise Forgejo's real /metrics endpoint and journal secret hygiene.

FORGEJO_TEST_BINARY enables the real-binary fixture. It verifies, against a
disposable SQLite instance:

  * /metrics is 401 without credentials and 200 with the exact bearer token
    that the NixOS module feeds to both Forgejo (metrics.TOKEN credential) and
    Prometheus (bearer_token_file);
  * the unauthenticated /api/healthz service-health signal is available;
  * neither the console log nor the metrics body ever contains the token
    value, so Loki-shipped journal lines cannot leak the scrape credential.

Run with FORGEJO_TEST_BINARY=/path/to/forgejo python3 -m unittest \
    scripts.tests.test_forgejo_metrics -v
"""
import json
import os
import secrets as pysecrets
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request(path, port, token=None):
    headers = {"Authorization": "Bearer " + token} if token else {}
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=2) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as response:
        return response.code, response.read().decode(errors="replace")


@unittest.skipUnless(os.environ.get("FORGEJO_TEST_BINARY"), "Set FORGEJO_TEST_BINARY for real metrics fixtures")
class RealMetricsTests(unittest.TestCase):
    def test_metrics_token_gating_and_secret_hygiene(self):
        binary = os.environ["FORGEJO_TEST_BINARY"]
        # Random per run: no literal credential is ever committed to the repo.
        metrics_token = pysecrets.token_hex(32)
        port = free_port()
        with tempfile.TemporaryDirectory() as directory:
            config = os.path.join(directory, "app.ini")
            with open(config, "w") as handle:
                handle.write(f"""[database]
DB_TYPE = sqlite3
PATH = {directory}/forgejo.db
[security]
INSTALL_LOCK = true
[server]
APP_DATA_PATH = {directory}/data
HTTP_ADDR = 127.0.0.1
HTTP_PORT = {port}
ROOT_URL = http://127.0.0.1:{port}/
DOMAIN = 127.0.0.1
DISABLE_SSH = true
[metrics]
ENABLED = true
TOKEN = {metrics_token}
[repository]
ROOT = {directory}/repositories
FORCE_PRIVATE = true
[service]
DISABLE_REGISTRATION = true
REQUIRE_SIGNIN_VIEW = true
[log]
MODE = console
LEVEL = Info
""")
            base = [binary, "--config", config, "--work-path", directory]
            for command in (
                ["migrate"],
                ["admin", "user", "create", "--username", "fixture",
                 "--email", "fixture@example.invalid", "--admin", "--random-password"],
            ):
                result = subprocess.run([*base, *command], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, "Fixture setup failed; output suppressed")

            log_path = os.path.join(directory, "web.console.log")
            with open(log_path, "wb") as console:
                process = subprocess.Popen([*base, "web"], stdout=console,
                                           stderr=console)
                try:
                    deadline = time.monotonic() + 30
                    while True:
                        try:
                            status, _ = request("/api/healthz", port)
                        except (OSError, urllib.error.URLError):
                            status = 0
                        if status == 200:
                            break
                        if process.poll() is not None or time.monotonic() > deadline:
                            self.fail("Fixture web process did not become ready")
                        time.sleep(0.1)

                    # Health signal used by the Grafana availability panels.
                    status, body = request("/api/healthz", port)
                    self.assertEqual(status, 200)
                    health = json.loads(body)
                    self.assertEqual(health["status"], "pass")
                    self.assertIn("database:ping", health["checks"])

                    # The private scrape contract: 401 bare, 200 with the
                    # exact token the NixOS module hands to Prometheus' bearer
                    # file.
                    status, _ = request("/metrics", port)
                    self.assertEqual(status, 401)
                    status, body = request("/metrics", port, token=metrics_token)
                    self.assertEqual(status, 200)
                    for expected in ("gitea_build_info", "gitea_repositories", "gitea_users"):
                        self.assertIn(expected, body)
                    self.assertNotIn(metrics_token, body)
                finally:
                    process.terminate()
                    process.wait(timeout=10)

            # The console log is what the journal (and therefore Loki) ships;
            # the scrape credential must never appear in it.
            with open(log_path, "r", errors="replace") as handle:
                console_text = handle.read()
            self.assertNotIn(metrics_token, console_text)
