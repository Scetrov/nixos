"""Offline checks for the bounded Hermes runtime deployment and encryption."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("render_hermes_secret", ROOT / "scripts/render_hermes_secret.py")
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


class HermesRuntimeDeployTests(unittest.TestCase):
    def invoke(self, *arguments):
        with tempfile.TemporaryDirectory() as directory:
            stub = Path(directory) / "ansible-playbook"
            stub.write_text('#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n')
            stub.chmod(0o755)
            return subprocess.run(
                ["bash", str(ROOT / "scripts/play.sh"), *arguments], cwd=ROOT,
                env={**os.environ, "PATH": directory + os.pathsep + os.environ["PATH"]},
                capture_output=True, text=True, check=False,
            )

    def test_focused_playbook_without_generated_secret_refresh(self):
        result = self.invoke("--limit", "habiki", "--tags", "hermes-runtime")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("src/hermes-runtime.yml", json.loads(result.stdout.splitlines()[-1]))
        self.assertNotIn("Refreshing", result.stdout)

    def test_rejects_scope_overrides(self):
        for arguments in [
            ["--tags", "hermes-runtime"],
            ["--limit", "fyne", "--tags", "hermes-runtime"],
            ["--limit", "habiki", "--tags", "hermes-runtime,nixos"],
            ["--limit", "habiki", "--tags", "hermes-runtime", "--", "--limit=all"],
            ["--limit", "habiki", "--tags", "hermes-runtime", "--", "--tags=nixos"],
            ["--limit", "habiki", "--tags", "hermes-runtime", "--", "--skip-tags=hermes-runtime"],
        ]:
            with self.subTest(arguments=arguments):
                result = self.invoke(*arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Error: hermes-runtime", result.stderr)

    def test_play_is_limited_and_secret_safe(self):
        source = (ROOT / "src/hermes-runtime.yml").read_text()
        play, = yaml.safe_load(source)
        self.assertEqual(play["hosts"], "habiki")
        self.assertEqual(play["vars_files"], ["secrets.yml"])
        self.assertNotIn("include_role", source)
        self.assertNotIn("tofu.sh", source)
        self.assertNotIn("nix-channel", source)
        tasks = {task["name"]: task for task in play["tasks"]}
        encrypt = tasks["Encrypt only the vault-rendered Hermes environment"]
        self.assertTrue(encrypt["no_log"])
        self.assertEqual(encrypt["when"], "not ansible_check_mode")
        self.assertIn("hermes-webui.env.j2", encrypt["ansible.builtin.command"]["stdin"])
        restart = tasks["Restart only the deployed Hermes application containers"]
        self.assertEqual(restart["loop"], ["podman-hermes-agent.service", "podman-hermes-webui.service"])
        version = tasks["Verify GitHub CLI inside both agent execution environments"]
        self.assertEqual(version["loop"], ["hermes-agent", "hermes-webui"])
        self.assertEqual(version["ansible.builtin.command"]["argv"],
                         ["podman", "exec", "{{ item }}", "gh", "--version"])


class HermesSecretEncryptionTests(unittest.TestCase):
    def test_plaintext_is_only_passed_to_age_stdin(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)

            def fake_age(command, **kwargs):
                self.assertEqual(command[:2], ["age", "--encrypt"])
                self.assertIn("--armor", command)
                self.assertEqual(command[-2:], ["--recipient", "fixture-public-key"])
                self.assertEqual(kwargs["input"], b"fixture-secret")
                Path(command[command.index("--output") + 1]).write_bytes(b"encrypted-fixture")

            with patch.object(renderer, "SECRETS", target), \
                    patch.object(renderer.subprocess, "check_output", return_value=b'["fixture-public-key"]'), \
                    patch.object(renderer.subprocess, "run", side_effect=fake_age):
                renderer.encrypt(b"fixture-secret")
            output = target / "hermes_webui_env.age"
            self.assertEqual(output.read_bytes(), b"encrypted-fixture")
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertEqual(list(target.iterdir()), [output])

    def test_encryption_failure_preserves_previous_ciphertext_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            output = target / "hermes_webui_env.age"
            output.write_bytes(b"previous-ciphertext")
            with patch.object(renderer, "SECRETS", target), \
                    patch.object(renderer.subprocess, "check_output", return_value=b'["fixture-public-key"]'), \
                    patch.object(renderer.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "age")):
                with self.assertRaises(subprocess.CalledProcessError):
                    renderer.encrypt(b"fixture-secret")
            self.assertEqual(output.read_bytes(), b"previous-ciphertext")
            self.assertEqual(list(target.iterdir()), [output])


if __name__ == "__main__":
    unittest.main()
