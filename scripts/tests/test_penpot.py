"""Offline Penpot deployment-contract tests; no live authentication claims."""
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request

from scripts.tests.test_render_generated_secrets import RenderError, render, valid_outputs

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "src/roles/nixos/files/etc/nixos/modules"
SPEC = importlib.util.spec_from_file_location("penpot_prepare_env", MODULES / "penpot-prepare-env.py")
prepare = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare)
NAMES = ("penpot_db_password", "penpot_secret_key", "penpot_oidc_client_id", "penpot_oidc_client_secret")


class RuntimeSecretTests(unittest.TestCase):
    def fixture(self, root):
        state, credentials = root / "state", root / "credentials"
        state.mkdir()
        credentials.mkdir()
        for name in NAMES:
            (credentials / name).write_text("synthetic-" + name)
        return state, credentials

    def test_render_separates_credentials_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as directory:
            state, credentials = self.fixture(Path(directory))
            prepare.render(state, credentials)
            before = {p.name: p.read_text() for p in state.iterdir()}
            self.assertEqual(len(before), 4)
            self.assertEqual(before["frontend.env"], "PENPOT_OIDC_CLIENT_ID=synthetic-penpot_oidc_client_id\n")
            self.assertNotIn("penpot_db_password", before["exporter.env"])
            self.assertNotIn("penpot_oidc_client_secret", before["postgres.env"])
            for path in state.iterdir():
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            prepare.render(state, credentials)
            self.assertEqual(before, {p.name: p.read_text() for p in state.iterdir()})
            (credentials / "penpot_oidc_client_secret").write_text("synthetic-rotation")
            prepare.render(state, credentials)
            self.assertIn("synthetic-rotation", (state / "backend.env").read_text())
            self.assertEqual(before["postgres.env"], (state / "postgres.env").read_text())

    def test_bad_credentials_fail_before_any_files_are_written(self):
        for value in ("", "null", "placeholder", "x_placeholder", "one\nINJECTED=two", "a\x00b"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                state, credentials = self.fixture(Path(directory))
                (credentials / "penpot_oidc_client_secret").write_text(value)
                with self.assertRaises(ValueError):
                    prepare.render(state, credentials)
                self.assertEqual(list(state.iterdir()), [])

    def test_missing_credential_fails_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            state, credentials = self.fixture(Path(directory))
            (credentials / "penpot_secret_key").unlink()
            with self.assertRaises(FileNotFoundError):
                prepare.render(state, credentials)
            self.assertEqual(list(state.iterdir()), [])

    def test_generated_manifest_requires_every_penpot_value(self):
        self.assertIn("penpot_oidc_client_secret: |", render(valid_outputs()))
        for name in NAMES:
            outputs = valid_outputs()
            del outputs[name]
            with self.subTest(name=name), self.assertRaises(RenderError):
                render(outputs)


class ConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run(
            ["nix-instantiate", "--eval", "--strict", "--json", "tests/penpot-eval.nix"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        cls.config = json.loads(result.stdout)

    def test_only_native_authentication_is_configured(self):
        flags = self.config["environment"]["PENPOT_FLAGS"].split()
        for flag in ("enable-login-with-oidc", "enable-oidc-registration", "disable-registration",
                     "disable-login-with-password", "disable-smtp", "enable-secure-session-cookies", "enable-mcp"):
            self.assertIn(flag, flags)
        self.assertNotIn("forward_auth http", self.config["virtualHost"])
        tofu = (ROOT / "terraform/penpot.tf").read_text()
        self.assertIn("authentik_group.all_applications.id", tofu)
        self.assertIn("https://penpot.net.scetrov.live/api/auth/oidc/callback", tofu)
        self.assertIn('client_type        = "confidential"', tofu)

    def test_query_keys_are_removed_from_proxy_logs(self):
        logging = self.config["runtimeLogging"]
        self.assertIn("request>uri query", logging)
        self.assertIn("delete userToken", logging)
        self.assertIn("request>headers>Referer delete", logging)
        source = (MODULES / "penpot.nix").read_text()
        self.assertIn("access_log off;", source)
        self.assertIn("error_log /dev/null;", source)
        self.assertIn("/tmp/nginx.conf.template:ro", source)

    @unittest.skipUnless(os.environ.get("CADDY_BINARY"), "Set CADDY_BINARY for isolated proxy-error log test")
    def test_caddy_error_log_redacts_synthetic_url_key(self):
        with socket.socket() as reserve:
            reserve.bind(("127.0.0.1", 0))
            port = reserve.getsockname()[1]
        canary = "synthetic-penpot-log-canary"
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory, "Caddyfile")
            config.write_text("{\nadmin off\nauto_https off\nlog {\n" + self.config["runtimeLogging"]
                              + "\n}\n}\nhttp://127.0.0.1:" + str(port)
                              + " {\nreverse_proxy 127.0.0.1:1\n}\n")
            process = subprocess.Popen(
                [os.environ["CADDY_BINARY"], "run", "--config", str(config), "--adapter", "caddyfile"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            try:
                for _ in range(100):
                    try:
                        urllib.request.urlopen(f"http://127.0.0.1:{port}/mcp/stream?userToken={canary}", timeout=1)
                    except urllib.error.HTTPError as error:
                        self.assertEqual(error.code, 502)
                        break
                    except urllib.error.URLError:
                        time.sleep(0.05)
                else:
                    self.fail("Isolated Caddy did not start")
            finally:
                process.terminate()
                stdout, stderr = process.communicate(timeout=10)
            logs = stdout + stderr
            self.assertNotIn(canary, logs)
            self.assertIn("connection refused", logs)
            self.assertIn('"status":502', logs)

    def test_targeted_deploy_rejects_scope_expansion(self):
        for arguments in (["--limit", "fyne", "--tags", "penpot"],
                          ["--limit", "habiki", "--tags", "penpot,nixos"],
                          ["--limit", "habiki", "--tags", "penpot", "--", "--limit=all"]):
            with self.subTest(arguments=arguments):
                result = subprocess.run(["scripts/play.sh", *arguments], cwd=ROOT, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Error: penpot", result.stderr)
        for file in ("main.yml", "rebuild.yml"):
            source = (ROOT / "src/roles/nixos/tasks" / file).read_text()
            conditions = [line for line in source.splitlines() if "not (nixos_filebrowser_only" in line]
            self.assertTrue(conditions)
            self.assertTrue(all("not (nixos_penpot_only" in line for line in conditions))

    def test_health_and_existing_telemetry_are_wired(self):
        self.assertEqual(len(self.config["readinessScrape"]), 1)
        # The alert ships as a standalone rule file (its own rule_files entry)
        # rather than being concatenated into the shared rules document, so it
        # cannot collide with another module's groups: key or indentation.
        self.assertEqual(len(self.config["ruleFiles"]), 1)
        self.assertTrue(self.config["ruleFiles"][0].startswith("/nix/store/"))
        source = (MODULES / "penpot.nix").read_text()
        self.assertIn('writeText "penpot-prometheus.rules"', source)
        self.assertIn("PenpotServiceUnavailable", source)
        self.assertNotIn("PenpotServiceUnavailable", "\n".join(self.config["rules"]))
        for name, options in self.config["healthOptions"].items():
            with self.subTest(name=name):
                self.assertIn("--log-driver=journald", options)
                self.assertIn("--health-on-failure=kill", options)
        for name in ("penpot-mcp", "penpot-exporter"):
            command = next(x.split("=", 1)[1] for x in self.config["healthOptions"][name] if x.startswith("--health-cmd="))
            self.assertEqual(json.loads(command)[:2], ["node", "-e"])
        self.assertIn('replacement   = "penpot"', (MODULES / "alloy.nix").read_text())
        self.assertIn('"penpot.net.scetrov.live"', (MODULES / "local-networking.nix").read_text())
        catalog = json.loads((ROOT / "terraform/dashboards/service-catalog.json").read_text())
        self.assertTrue(any("Open Penpot" in p.get("options", {}).get("content", "") for p in catalog["panels"]))


if __name__ == "__main__":
    unittest.main()
