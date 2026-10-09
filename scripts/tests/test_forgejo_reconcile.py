"""Non-sensitive identity fixtures, including the actual selected Forgejo CLI.

FORGEJO_TEST_BINARY enables real SQLite first/repeat/rotation tests. Production
reconciliation uses only supported CLI interfaces, never database writes.
"""
import contextlib
import http.server
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import socket
import subprocess
import time
import urllib.request
import tempfile
import threading
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[2] / "src/roles/nixos/files/etc/nixos/modules/forgejo-reconcile.py"
spec = importlib.util.spec_from_file_location("reconcile", MODULE)
reconcile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reconcile)
registration_spec = importlib.util.spec_from_file_location("registration", MODULE.with_name("forgejo-runner-register.py"))
registration = importlib.util.module_from_spec(registration_spec)
registration_spec.loader.exec_module(registration)


class ReconcileTests(unittest.TestCase):
    def test_source_listing(self):
        self.assertIsNone(reconcile.source_id("ID\tName\tType\tEnabled\n"))
        self.assertEqual(reconcile.source_id("ID Name Type Enabled\n7 authentik OAuth2 true\n"), "7")
        for output in ["broken", "ID Name Type Enabled\n1 authentik LDAP true\n",
                       "ID Name Type Enabled\n1 authentik OAuth2 true\n2 authentik OAuth2 true\n"]:
            with self.assertRaises(reconcile.ReconcileError):
                reconcile.source_id(output)

    def test_invalid_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credential"
            for value in ["", " ", "a b", "fixture_placeholder"]:
                path.write_text(value)
                with self.assertRaises(reconcile.ReconcileError):
                    reconcile.credential(path)

    def test_command_errors_never_include_secret(self):
        command = ["forgejo", "--secret", "fixture-sensitive-sentinel"]
        errors = [OSError("fixture-sensitive-sentinel"),
                  subprocess.TimeoutExpired(command, 90, output="fixture-sensitive-sentinel")]
        for error in errors:
            with patch.object(reconcile.subprocess, "run", side_effect=error):
                with self.assertRaises(reconcile.ReconcileError) as caught:
                    reconcile.run(command)
                self.assertNotIn("fixture-sensitive-sentinel", str(caught.exception))
        with patch.object(reconcile.subprocess, "run", return_value=subprocess.CompletedProcess(
            command, 1, "fixture-sensitive-sentinel", "fixture-sensitive-sentinel")):
            with self.assertRaises(reconcile.ReconcileError) as caught:
                reconcile.run(command)
            self.assertNotIn("fixture-sensitive-sentinel", str(caught.exception))

    def test_registration_retries_keep_identity_and_use_stdin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template.json"
            template.write_text(json.dumps({"runner": {"labels": []}}))
            args = ("fixture", "fixture", "fixture", root, template, "https://fixture", "fixture")
            with patch.object(registration.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "")) as command:
                with self.assertRaises(registration.RegistrationError):
                    registration.register(*args)
            token = (root / "token").read_text()
            self.assertIn("--secret-stdin", command.call_args.args[0])
            self.assertNotIn(token, command.call_args.args[0])
            self.assertEqual(command.call_args.kwargs["input"], token)
            with patch.object(registration.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "")):
                with self.assertRaises(registration.RegistrationError):
                    registration.register(*args)
            self.assertEqual((root / "token").read_text(), token)
            for forbidden in ["", "fixture/repo"]:
                with self.assertRaises(registration.RegistrationError):
                    registration.register(*args[:-1], forbidden)

    def test_main_suppresses_file_errors(self):
        stderr = io.StringIO()
        with patch.dict(os.environ, {"CREDENTIALS_DIRECTORY": "/nonexistent-fixture"}), \
             patch.object(reconcile.sys, "argv", ["reconcile", "--binary", "fixture",
                "--config", "fixture", "--work-path", "fixture", "--discovery-url", "https://fixture"]), \
             contextlib.redirect_stderr(stderr):
            self.assertEqual(reconcile.main(), 1)
        self.assertEqual(stderr.getvalue(), "Forgejo OIDC reconciliation failed; sensitive diagnostics suppressed\n")


@unittest.skipUnless(os.environ.get("FORGEJO_TEST_BINARY"), "Set FORGEJO_TEST_BINARY for real CLI fixtures")
class RealCLITests(unittest.TestCase):
    def test_restart_and_stopped_service_retain_repositories_and_ssh_keys(self):
        def free_port():
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                return sock.getsockname()[1]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db, config, key = root / "forgejo.db", root / "app.ini", root / "data/ssh/forgejo.rsa"
            port, ssh_port = free_port(), free_port()
            config.write_text(f"""[database]
DB_TYPE = sqlite3
PATH = {db}
[security]
INSTALL_LOCK = true
[server]
APP_DATA_PATH = {root}/data
HTTP_ADDR = 127.0.0.1
HTTP_PORT = {port}
ROOT_URL = http://127.0.0.1:{port}/
START_SSH_SERVER = true
SSH_LISTEN_HOST = 127.0.0.1
SSH_LISTEN_PORT = {ssh_port}
SSH_PORT = {ssh_port}
SSH_SERVER_HOST_KEYS = {key}
[repository]
ROOT = {root}/repositories
FORCE_PRIVATE = true
[service]
DISABLE_REGISTRATION = true
REQUIRE_SIGNIN_VIEW = true
ENABLE_INTERNAL_SIGNIN = false
ENABLE_BASIC_AUTHENTICATION = false
[log]
MODE = console
LEVEL = Error
""")
            binary = os.environ["FORGEJO_TEST_BINARY"]
            base = [binary, "--config", str(config), "--work-path", directory]
            for command in [["migrate"], ["admin", "user", "create", "--username", "fixture",
                    "--email", "fixture@example.invalid", "--admin", "--random-password"]]:
                result = subprocess.run([*base, *command], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, "Fixture setup failed; output suppressed")
            result = subprocess.run([*base, "admin", "user", "generate-access-token",
                "--username", "fixture", "--token-name", "fixture", "--scopes", "all", "--raw"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            token = result.stdout.strip().splitlines()[-1]

            def request(path, data=None):
                body = None if data is None else json.dumps(data).encode()
                req = urllib.request.Request(f"http://127.0.0.1:{port}" + path, body,
                    headers={"Authorization": "token " + token, "Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=2) as response:
                    return json.load(response)

            original_key = None
            for iteration in range(2):
                # Models the upstream rebuild preStart migration followed by web startup.
                result = subprocess.run([*base, "migrate"], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0)
                process = subprocess.Popen([*base, "web"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    deadline = time.monotonic() + 30
                    while True:
                        try:
                            request("/api/v1/version")
                            break
                        except (OSError, ValueError):
                            if process.poll() is not None or time.monotonic() > deadline:
                                self.fail("Fixture web process did not become ready")
                            time.sleep(0.1)
                    if iteration == 0:
                        # Real supported pre-registration + authenticated Declare:
                        # first/repeat/rotation use one UUID and one active record.
                        control = root / "control"
                        control.mkdir(mode=0o700)
                        template = root / "runner-template.json"
                        template.write_text(json.dumps({"runner": {"labels": []}}))
                        args = (binary, str(config), directory, control, template,
                                f"http://127.0.0.1:{port}/", "fixture")
                        registration.register(*args)
                        original_token = (control / "token").read_text()
                        original_uuid = (control / "uuid").read_text()
                        registration.register(*args)
                        self.assertEqual((control / "token").read_text(), original_token)
                        registration.register(*args, rotate=True)
                        self.assertNotEqual((control / "token").read_text(), original_token)
                        self.assertEqual((control / "uuid").read_text(), original_uuid)
                        with contextlib.closing(sqlite3.connect(f"file:{db}?mode=ro", uri=True)) as connection:
                            runners = connection.execute("SELECT id, uuid, owner_id, repo_id FROM action_runner WHERE deleted IS NULL OR deleted = 0").fetchall()
                        self.assertEqual(len(runners), 1)
                        self.assertGreater(runners[0][2], 0)
                        self.assertEqual(runners[0][3], 0)
                        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/v1/user/actions/runners/{runners[0][0]}",
                            method="DELETE", headers={"Authorization": "token " + token})
                        with urllib.request.urlopen(req, timeout=2) as response:
                            self.assertEqual(response.status, 204)
                        with self.assertRaises(registration.RegistrationError):
                            registration.register(*args)
                        registration.register(*args, recover=True)
                        self.assertEqual((control / "uuid").read_text(), original_uuid)
                        with contextlib.closing(sqlite3.connect(f"file:{db}?mode=ro", uri=True)) as connection:
                            self.assertEqual(connection.execute("SELECT COUNT(*) FROM action_runner WHERE deleted IS NULL OR deleted = 0").fetchone()[0], 1)
                            self.assertEqual(connection.execute("SELECT COUNT(*) FROM action_runner WHERE deleted != 0").fetchone()[0], 1)
                        self.assertNotIn((control / "token").read_text(), (control / "config.yaml").read_text())
                        self.assertEqual((control / "token").stat().st_mode & 0o777, 0o600)
                        request("/api/v1/user/repos", {"name": "persistent-fixture", "private": True,
                                "auto_init": True})
                        original_key = key.read_bytes()
                    repo = request("/api/v1/repos/fixture/persistent-fixture")
                    self.assertTrue(repo["private"])
                    self.assertEqual(key.read_bytes(), original_key)
                    self.assertTrue(request("/api/v1/repos/fixture/persistent-fixture/contents/README.md"))
                finally:
                    process.terminate()
                    process.wait(timeout=15)
                # Stopping/disablement must leave data intact and close both listeners.
                self.assertTrue(db.exists())
                self.assertTrue((root / "repositories/fixture/persistent-fixture.git/HEAD").exists())
                self.assertEqual(key.read_bytes(), original_key)
                for listener in (port, ssh_port):
                    with socket.socket() as sock:
                        self.assertNotEqual(sock.connect_ex(("127.0.0.1", listener)), 0)

    def test_first_repeat_rotate_and_claim_mapping(self):
        class Discovery(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                issuer = f"http://127.0.0.1:{self.server.server_port}"
                body = json.dumps({"issuer": issuer, "authorization_endpoint": issuer + "/authorize",
                                   "token_endpoint": issuer + "/token", "jwks_uri": issuer + "/jwks",
                                   "userinfo_endpoint": issuer + "/userinfo"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Discovery)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                db = root / "forgejo.db"
                config = root / "app.ini"
                config.write_text(f"""[database]
DB_TYPE = sqlite3
PATH = {db}
[security]
INSTALL_LOCK = true
[server]
APP_DATA_PATH = {root}/data
[log]
MODE = console
LEVEL = Error
""")
                binary = os.environ["FORGEJO_TEST_BINARY"]
                result = subprocess.run([binary, "--config", str(config), "--work-path", directory,
                                         "migrate"], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                client_id, secret = root / "client-id", root / "client-secret"
                client_id.write_text("fixture-client-id")
                url = f"http://127.0.0.1:{server.server_port}/.well-known/openid-configuration"
                previous_id = None
                for value in ["fixture-secret-original", "fixture-secret-original", "fixture-secret-rotated"]:
                    secret.write_text(value)
                    reconcile.reconcile(binary, str(config), directory, client_id, secret, url)
                    # Read-only inspection in a disposable fixture, not production writes.
                    with contextlib.closing(sqlite3.connect(f"file:{db}?mode=ro", uri=True)) as connection:
                        rows = connection.execute("SELECT id, name, cfg FROM login_source").fetchall()
                    self.assertEqual(len(rows), 1)
                    source, name, cfg = rows[0]
                    if previous_id is not None:
                        self.assertEqual(source, previous_id)
                    previous_id = source
                    self.assertEqual(name, "authentik")
                    cfg = json.loads(cfg)
                    self.assertEqual(cfg["ClientSecret"], value)
                    self.assertEqual(cfg["RequiredClaimName"], "groups")
                    self.assertEqual(cfg["RequiredClaimValue"], "Forgejo Owners")
                    self.assertEqual(cfg["GroupClaimName"], "groups")
                    self.assertEqual(cfg["AdminGroup"], "Forgejo Owners")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
