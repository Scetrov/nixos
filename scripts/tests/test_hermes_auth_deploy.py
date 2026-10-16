"""Sandbox-safe tests for the proxy-only deployment entrypoint."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class HermesAuthDeployTests(unittest.TestCase):
    def invoke(self, *arguments):
        with tempfile.TemporaryDirectory() as directory:
            stub = Path(directory) / "ansible-playbook"
            stub.write_text('#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n')
            stub.chmod(0o755)
            return subprocess.run(
                ["bash", str(ROOT / "scripts/play.sh"), *arguments],
                cwd=ROOT,
                env={**os.environ, "PATH": directory + os.pathsep + os.environ["PATH"]},
                capture_output=True,
                text=True,
                check=False,
            )

    def test_focused_playbook_and_no_secret_refresh(self):
        result = self.invoke("--limit", "habiki", "--tags", "hermes-auth")
        self.assertEqual(result.returncode, 0, result.stderr)
        arguments = json.loads(result.stdout.splitlines()[-1])
        self.assertIn("src/hermes-auth.yml", arguments)
        self.assertEqual(arguments[-4:], ["--limit", "habiki", "--tags", "hermes-auth"])
        self.assertNotIn("Refreshing", result.stdout)
        playbook = (ROOT / "src/hermes-auth.yml").read_text()
        self.assertNotIn("nix-channel", playbook)
        self.assertNotIn("state: restarted", playbook)
        self.assertNotIn("secrets.yml", playbook)

    def test_rejects_wrong_host_and_mixed_tags(self):
        for arguments in [
            ["--tags", "hermes-auth"],
            ["--limit", "fyne", "--tags", "hermes-auth"],
            ["--limit", "habiki", "--tags", "hermes-auth,nixos"],
            ["--limit", "habiki", "--tags", "hermes-auth", "--", "--limit=all"],
            ["--limit", "habiki", "--tags", "hermes-auth", "--", "--tags=nixos"],
        ]:
            with self.subTest(arguments=arguments):
                result = self.invoke(*arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Error: hermes-auth", result.stderr)


if __name__ == "__main__":
    unittest.main()
