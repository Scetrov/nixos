"""Broker token exchange, ownership gate, and Vault persistence fixtures."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.garage_broker import (
    ACCESS_KEY_NAME,
    BrokerError,
    SECRET_KEY_NAME,
    exchange_token,
    ownership_conflict,
    persist_admin_token,
    persist_pair,
    prepare,
)


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class Opener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def open(self, request, timeout=30):
        self.requests.append(request)
        return Response(self.responses.pop(0))


class ExchangeTests(unittest.TestCase):
    def test_prepare_returns_only_the_machine_jwt(self):
        opener = Opener([
            {"access_token": "header.payload.signature"},
            [{"globalAliases": ["other"]}],
            [{"name": "other-backup"}],
        ])
        token = prepare(
            "garage_admin_broker_client_id: client\ngarage_admin_broker_app_password: app-password\n",
            set(), opener=opener,
        )
        self.assertEqual(token, "header.payload.signature")
        self.assertIn("username=garage-admin-broker", opener.requests[0].data.decode())
        self.assertEqual(opener.requests[1].get_header("Authorization"), "Bearer header.payload.signature")
        self.assertNotIn("app-password", opener.requests[1].get_header("Authorization"))

    def test_missing_generated_credentials_stay_disabled(self):
        self.assertEqual(prepare("", set()), "disabled")

    def test_existing_unowned_bucket_blocks_adoption(self):
        with self.assertRaises(BrokerError):
            prepare(
                "garage_admin_broker_client_id: client\ngarage_admin_broker_app_password: app-password\n",
                set(),
                opener=Opener([
                    {"access_token": "header.payload.signature"},
                    [{"globalAliases": ["minecraft"]}],
                    [],
                ]),
            )

    def test_state_owned_bucket_is_not_a_conflict(self):
        self.assertIsNone(ownership_conflict(
            [{"globalAliases": ["minecraft"]}],
            [{"name": "minecraft-backup"}],
            {"garage_bucket.minecraft[0]", "garage_key.minecraft[0]"},
        ))


class VaultTests(unittest.TestCase):
    def _run(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        if argv[1] == "view":
            return subprocess.CompletedProcess(argv, 0, stdout=self.view)
        plaintext = kwargs["input"]
        self.written = plaintext
        Path(argv[argv.index("--output") + 1]).write_text("$ANSIBLE_VAULT;encrypted\n")
        return subprocess.CompletedProcess(argv, 0, stdout="")

    def setUp(self):
        self.calls = []
        self.view = "unrelated: kept\n"
        self.written = ""

    def test_pair_is_appended_without_replacing_unrelated_values(self):
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory) / "secrets.yml"
            vault.write_text("$ANSIBLE_VAULT;old\n")
            outputs = {
                "garage_minecraft_access_key_id": {"value": "AKIAFIXEDKEY1234567", "sensitive": True},
                "garage_minecraft_secret_access_key": {"value": "secret-fixture-value", "sensitive": True},
            }
            with patch("scripts.garage_broker.subprocess.run", side_effect=self._run):
                self.assertEqual(persist_pair(vault, Path("password"), outputs), "created")
            self.assertIn("unrelated: kept\n", self.written)
            self.assertIn(ACCESS_KEY_NAME, self.written)
            self.assertNotIn("secret-fixture-value", " ".join(self.calls[1][0]))
            self.assertTrue(vault.read_text().startswith("$ANSIBLE_VAULT;"))

    def test_failed_encryption_preserves_vault_and_retry_uses_the_same_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory) / "secrets.yml"
            vault.write_text("$ANSIBLE_VAULT;old\n")
            outputs = {
                "garage_minecraft_access_key_id": {"value": "AKIAFIXEDKEY1234567", "sensitive": True},
                "garage_minecraft_secret_access_key": {"value": "secret-fixture-value", "sensitive": True},
            }

            def fail_once(argv, **kwargs):
                if argv[1] == "encrypt":
                    return subprocess.CompletedProcess(argv, 1, stdout="", stderr="encryption failed")
                return self._run(argv, **kwargs)

            with patch("scripts.garage_broker.subprocess.run", side_effect=fail_once):
                with self.assertRaises(BrokerError):
                    persist_pair(vault, Path("password"), outputs)
            self.assertEqual(vault.read_text(), "$ANSIBLE_VAULT;old\n")
            with patch("scripts.garage_broker.subprocess.run", side_effect=self._run):
                self.assertEqual(persist_pair(vault, Path("password"), outputs), "created")
            self.assertEqual(self.written.count("AKIAFIXEDKEY1234567"), 1)

    def test_different_existing_pair_is_not_rotated(self):
        self.view = (
            'unrelated: kept\n'
            + ACCESS_KEY_NAME + ': "AKIAOTHERKEY12345678"\n'
            + SECRET_KEY_NAME + ': "other-secret"\n'
        )
        outputs = {
            "garage_minecraft_access_key_id": {"value": "AKIAFIXEDKEY1234567", "sensitive": True},
            "garage_minecraft_secret_access_key": {"value": "secret-fixture-value", "sensitive": True},
        }
        with patch("scripts.garage_broker.subprocess.run", side_effect=self._run):
            with self.assertRaises(BrokerError):
                persist_pair(Path("vault"), Path("password"), outputs)
        self.assertEqual(len(self.calls), 1)

    def test_admin_token_persistence_accepts_the_published_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory) / "secrets.yml"
            vault.write_text("$ANSIBLE_VAULT;old\n")
            payload = {"secretToken": "ab" * 12 + "." + "b" * 43}
            with patch("scripts.garage_broker.subprocess.run", side_effect=self._run):
                self.assertEqual(persist_admin_token(vault, Path("password"), payload), "created")
            self.assertIn("unrelated: kept", self.written)
            self.assertNotIn("b" * 43, " ".join(self.calls[1][0]))

    def test_admin_token_persistence_rejects_malformed_output(self):
        with patch("scripts.garage_broker.subprocess.run", side_effect=self._run):
            with self.assertRaises(BrokerError):
                persist_admin_token(Path("vault"), Path("password"), {"secretToken": "not-a-token"})


class ExchangeFailureTests(unittest.TestCase):
    def test_non_jwt_is_rejected(self):
        with self.assertRaises(BrokerError):
            exchange_token("client", "password", opener=Opener([{"access_token": "opaque"}]))


if __name__ == "__main__":
    unittest.main()
