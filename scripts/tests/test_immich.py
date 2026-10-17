"""Immich integration checks; all credentials below are synthetic fixtures."""
import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_render_generated_secrets import RenderError, render, valid_outputs

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "src/roles/nixos/files/etc/nixos/modules"
spec = importlib.util.spec_from_file_location("immich_bootstrap", MODULES / "immich-bootstrap.py")
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)
vault_spec = importlib.util.spec_from_file_location("immich_vault", ROOT / "scripts/provision_immich_vault.py")
vault = importlib.util.module_from_spec(vault_spec)
vault_spec.loader.exec_module(vault)


class BootstrapTests(unittest.TestCase):
    def run_bootstrap(self, initialized=True, admin=True):
        calls = []

        def api(path, body=None, token=None):
            calls.append((path, body, token))
            if path == "/server/config":
                return {"isInitialized": initialized}
            if path == "/auth/login":
                return {"isAdmin": admin, "userEmail": "git@scetrov.live", "accessToken": "fixture-token"}
            return {}

        with patch.object(bootstrap, "credential", side_effect=lambda name: {
            "admin-email": "git@scetrov.live", "admin-password": "synthetic-password-" * 4,
        }[name]), patch.object(bootstrap, "request", side_effect=api):
            bootstrap.bootstrap()
        return calls

    def test_first_start_creates_admin_and_verifies_login(self):
        calls = self.run_bootstrap(initialized=False)
        self.assertEqual([c[0] for c in calls], ["/server/config", "/auth/admin-sign-up", "/auth/login", "/auth/logout"])
        self.assertEqual(calls[1][1]["email"], "git@scetrov.live")
        self.assertEqual(calls[-1][2], "fixture-token")

    def test_repeated_start_does_not_reset_or_create_users(self):
        self.assertEqual([c[0] for c in self.run_bootstrap()], ["/server/config", "/auth/login", "/auth/logout"])

    def test_non_admin_is_rejected(self):
        with self.assertRaises(ValueError):
            self.run_bootstrap(admin=False)

    def test_unexpected_existing_identity_fails_without_reset(self):
        with patch.object(bootstrap, "credential", return_value="unexpected"), self.assertRaises(ValueError):
            bootstrap.bootstrap()

    def test_missing_and_placeholder_credentials_fail(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, CREDENTIALS_DIRECTORY=directory):
            with self.assertRaises(FileNotFoundError):
                bootstrap.credential("missing")
            for value in ["", "null", "changeme", "PASSWORD_PLACEHOLDER"]:
                Path(directory, "admin-password").write_text(value)
                with self.assertRaises(ValueError):
                    bootstrap.credential("admin-password")


class VaultTests(unittest.TestCase):
    def test_existing_password_is_not_rotated(self):
        view = 'immich_admin_email: git@scetrov.live\nimmich_admin_password: "' + 'x' * 64 + '"\n'
        with patch.object(vault.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout=view)) as run:
            self.assertFalse(vault.provision(Path("unused"), Path("unused")))
            self.assertEqual(run.call_count, 1)

    def test_invalid_existing_credentials_fail_without_overwrite(self):
        for value in ['null', '"short"', '123', '"' + 'x' * 40 + '_placeholder"']:
            with self.subTest(value=value), patch.object(vault.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout='immich_admin_password: ' + value)) as run:
                with self.assertRaises(ValueError):
                    vault.provision(Path("unused"), Path("unused"))
                self.assertEqual(run.call_count, 1)

    def test_new_password_is_encrypted_before_replacing_vault(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory, "secrets.yml")
            target.write_text("original ciphertext")

            def process(args, **kwargs):
                if "view" in args:
                    return subprocess.CompletedProcess(args, 0, stdout="existing: preserved\n")
                self.assertNotIn("fixture-password", " ".join(args))
                self.assertIn("existing: preserved", kwargs["input"])
                self.assertIn('immich_admin_email: "git@scetrov.live"', kwargs["input"])
                Path(args[args.index("--output") + 1]).write_text("$ANSIBLE_VAULT;synthetic ciphertext")
                return subprocess.CompletedProcess(args, 0)

            with patch.object(vault.subprocess, "run", side_effect=process), patch.object(vault.secrets, "token_hex", return_value="fixture-password"):
                self.assertTrue(vault.provision(target, Path("unused")))
            self.assertTrue(target.read_text().startswith("$ANSIBLE_VAULT;"))
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)


class IntegrationTests(unittest.TestCase):
    def test_generated_credentials_reject_invalid_values(self):
        for key in ("immich_oidc_client_id", "immich_oidc_client_secret"):
            outputs = valid_outputs()
            del outputs[key]
            with self.assertRaises(RenderError):
                render(outputs)
            for value in [None, "", "null", "PLACEHOLDER", "id_placeholder"]:
                with self.assertRaises(RenderError):
                    render(valid_outputs(**{key: {"value": value}}))
        self.assertIn("immich-secret-fixture", render(valid_outputs()))

    def test_exact_callbacks_and_access_policy(self):
        text = (ROOT / "terraform/authentik.tf").read_text()
        provider = text.split('resource "authentik_provider_oauth2" "immich" {')[1].split('resource "authentik_application" "immich"')[0]
        for callback in ["https://immich.net.scetrov.live/auth/login", "https://immich.net.scetrov.live/user-settings", "app.immich:///oauth-callback"]:
            self.assertIn('"' + callback + '"', provider)
        self.assertIn('matching_mode     = "strict"', provider)
        binding = text.split('resource "authentik_policy_binding" "immich_access" {')[1].split("}")[0]
        self.assertIn("authentik_group.all_applications.id", binding)
        self.assertNotIn("general_user", binding)
        for key in ["client_id", "client_secret"]:
            output = text.split('output "immich_oidc_' + key + '" {')[1].split("}")[0]
            self.assertIn("sensitive = true", output)
            self.assertIn("authentik_provider_oauth2.immich." + key, output)

    def test_official_application_icon_is_locally_deployed(self):
        import hashlib
        import struct

        icon = ROOT / "src/roles/nixos/files/etc/nixos/branding/immich-a4cda3df8fe5.png"
        data = icon.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), "a4cda3df8fe52ccf11431cf691ebbfcbc3694d4d8b4d922d6ae43fedf25c43ff")
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", data[16:24]), (512, 512))
        self.assertIn(icon.name, (ROOT / "src/roles/nixos/tasks/main.yml").read_text())
        application = (ROOT / "terraform/authentik.tf").read_text().split('resource "authentik_application" "immich" {')[1].split("}")[0]
        self.assertIn('meta_icon          = "/static/dist/branding/' + icon.name + '"', application)

    def test_runtime_secret_wiring(self):
        nix = (MODULES / "immich.nix").read_text()
        ansible = (ROOT / "src/roles/secrets/tasks/immich.yml").read_text()
        recipients = (ROOT / "src/roles/secrets/files/secrets/secrets.nix").read_text()
        for key in ["immich_oidc_client_id", "immich_oidc_client_secret", "immich_admin_email", "immich_admin_password"]:
            self.assertIn(key + ".age", nix)
            self.assertIn("'name': '" + key + "'", ansible)
            self.assertIn('"' + key + '.age".publicKeys = users ++ [ habiki ];', recipients)
        self.assertIn("clientSecret._secret = config.age.secrets.immich_oidc_client_secret.path", nix)
        self.assertIn("clientId._secret = config.age.secrets.immich_oidc_client_id.path", nix)
        self.assertIn('mode = "0400";', nix)
        self.assertIn("no_log: true", ansible)
        self.assertIn("immich_admin_password | length >= 32", ansible)

    def test_proxy_and_recovery_settings(self):
        nix = (MODULES / "immich.nix").read_text()
        self.assertIn('host = "127.0.0.1";', nix)
        self.assertIn("openFirewall = false;", nix)
        self.assertIn('useACMEHost = "scetrov.live";', nix)
        self.assertIn("reverse_proxy 127.0.0.1:3000", nix)
        self.assertNotIn("forward_auth", nix)
        self.assertIn("passwordLogin.enabled = true;", nix)
        self.assertIn("autoLaunch = false;", nix)
        self.assertIn("ExecStartPost", nix)

    def test_target_guards_run_without_credentials(self):
        for args in [["--tags", "immich"], ["--limit", "habiki", "--tags", "immich", "--skip-generated-refresh"], ["--limit", "habiki", "--tags", "immich,nixos"], ["--limit", "habiki", "--tags", "immich", "--", "--limit", "all"]]:
            result = subprocess.run(["bash", "scripts/play.sh", *args], cwd=ROOT, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"Error:", result.stderr)


if __name__ == "__main__":
    unittest.main()
