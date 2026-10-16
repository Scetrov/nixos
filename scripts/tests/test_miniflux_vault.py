"""Check Vault provisioning using non-sensitive fixtures and a mocked vault CLI."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.provision_miniflux_vault import provision


class VaultTests(unittest.TestCase):
    def test_create_encrypts_through_stdin_and_preserves_existing_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory) / "vault.yml"
            vault.write_text("$ANSIBLE_VAULT;fixture\n")
            calls = []

            def run(argv, **kwargs):
                calls.append((argv, kwargs))
                if argv[1] == "view":
                    return subprocess.CompletedProcess(argv, 0, stdout="existing: fixture\n")
                self.assertNotIn("miniflux_db_password", " ".join(argv))
                plaintext = kwargs["input"]
                self.assertTrue(plaintext.startswith("existing: fixture\n"))
                value = json.loads(plaintext.split("miniflux_db_password: ")[1])
                self.assertEqual(len(value), 64)
                Path(argv[argv.index("--output") + 1]).write_text("$ANSIBLE_VAULT;encrypted-fixture\n")
                return subprocess.CompletedProcess(argv, 0, stdout="")

            with patch("scripts.provision_miniflux_vault.subprocess.run", side_effect=run):
                self.assertTrue(provision(vault, Path("password-file")))
            self.assertEqual(len(calls), 2)
            self.assertTrue(vault.read_text().startswith("$ANSIBLE_VAULT;"))
            self.assertEqual(list(Path(directory).iterdir()), [vault])

    def test_existing_password_is_not_rotated(self):
        with patch("scripts.provision_miniflux_vault.subprocess.run") as run:
            run.return_value.stdout = 'miniflux_db_password: "' + "fixture" * 8 + '"\n'
            self.assertFalse(provision(Path("vault"), Path("password-file")))
            run.assert_called_once()

    def test_invalid_password_fails_instead_of_rotating(self):
        with patch("scripts.provision_miniflux_vault.subprocess.run") as run:
            run.return_value.stdout = "miniflux_db_password: placeholder\n"
            with self.assertRaises(ValueError):
                provision(Path("vault"), Path("password-file"))
            run.assert_called_once()
