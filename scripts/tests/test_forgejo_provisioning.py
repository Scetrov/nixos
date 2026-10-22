"""Credential persistence and pinned-provider guard tests; no live services."""
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("forgejo_provision_unit", ROOT / "scripts/provision_forgejo_mirrors.py")
provision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provision)


class CommandTests(unittest.TestCase):
    def test_only_initial_missing_state_is_allowed(self):
        absent = SimpleNamespace(returncode=1, stdout="", stderr="No state file was found!")
        with mock.patch.object(provision.subprocess, "run", return_value=absent):
            self.assertEqual(provision.command(["wrapper", "state", "list"], missing_state=True), "")
            with self.assertRaises(provision.ProvisionError):
                provision.command(["wrapper", "state", "list"])
        denied = SimpleNamespace(returncode=1, stdout="", stderr="permission denied: sensitive detail")
        with mock.patch.object(provision.subprocess, "run", return_value=denied):
            with self.assertRaisesRegex(provision.ProvisionError, "sensitive output suppressed"):
                provision.command(["wrapper", "state", "list"], missing_state=True)


class VaultTests(unittest.TestCase):
    def test_append_preserves_plaintext_and_only_installs_encrypted_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary) / "vault.yml"
            vault.write_text("$ANSIBLE_VAULT;existing")
            plain = "# keep comments\nunrelated_key: keep-me\n"
            credential = "a" * 64
            calls = []
            def run(args, **kwargs):
                calls.append((args, kwargs))
                if args[1] == "view":
                    return plain
                self.assertEqual(kwargs["input"], plain + "forgejo_mirrors_password: " + credential + "\n")
                Path(args[args.index("--output") + 1]).write_text("$ANSIBLE_VAULT;new-ciphertext")
                return ""
            with mock.patch.object(provision, "command", side_effect=run):
                provision.vault_add(vault, Path(temporary) / "password", "forgejo_mirrors_password", credential)
            self.assertEqual(vault.read_text(), "$ANSIBLE_VAULT;new-ciphertext")
            self.assertEqual(vault.stat().st_mode & 0o777, 0o600)
            self.assertTrue(all(credential not in " ".join(args) for args, _ in calls))

    def test_existing_credential_is_idempotent_and_replacement_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary) / "vault.yml"
            vault.write_text("$ANSIBLE_VAULT;existing")
            credential = "b" * 40
            with mock.patch.object(provision, "vault_read", return_value="forgejo_mirrors_token: " + credential + "\n"), \
                    mock.patch.object(provision, "command") as command:
                provision.vault_add(vault, Path(temporary) / "password", "forgejo_mirrors_token", credential)
                command.assert_not_called()
                with self.assertRaises(provision.ProvisionError):
                    provision.vault_add(vault, Path(temporary) / "password", "forgejo_mirrors_token", "c" * 40)

    def test_invalid_and_ambiguous_credentials_rejected(self):
        for text in ["forgejo_mirrors_token: placeholder", "forgejo_mirrors_token: secret\nforgejo_mirrors_token: duplicate"]:
            with self.assertRaises(provision.ProvisionError):
                provision.vault_value(text, "forgejo_mirrors_token")

    def test_concurrent_vault_edit_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary) / "vault.yml"
            vault.write_text("$ANSIBLE_VAULT;existing")
            def run(args, **kwargs):
                if args[1] == "view":
                    return "unrelated_key: keep-me\n"
                Path(args[args.index("--output") + 1]).write_text("$ANSIBLE_VAULT;new-ciphertext")
                vault.write_text("$ANSIBLE_VAULT;concurrent-editor")
                return ""
            with mock.patch.object(provision, "command", side_effect=run):
                with self.assertRaisesRegex(provision.ProvisionError, "concurrently"):
                    provision.vault_add(vault, Path(temporary) / "password", "forgejo_mirrors_token", "c" * 40)
            self.assertEqual(vault.read_text(), "$ANSIBLE_VAULT;concurrent-editor")


if __name__ == "__main__":
    unittest.main()
