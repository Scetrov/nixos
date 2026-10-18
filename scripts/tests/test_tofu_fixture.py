"""Ensure disposable OpenTofu tests cannot enter the production wrapper path."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "scripts/tofu.sh"


class FixtureWrapperTests(unittest.TestCase):
    def test_fixture_mode_has_explicit_command_and_drops_production_credentials(self):
        with tempfile.TemporaryDirectory(prefix=".passkey-test-", dir=ROOT / "terraform") as directory:
            fixture = Path(directory)
            binary = fixture / "bin"
            binary.mkdir()
            fake = binary / "tofu"
            fake.write_text(
                '#!/bin/sh\n'
                'test -z "${PG_CONN_STR+x}${TF_VAR_authentik_token+x}${TF_VAR_grafana_token+x}" || exit 71\n'
                'printf "%s\\n" "$@"\n'
            )
            fake.chmod(0o700)
            env = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ["PATH"],
                       PG_CONN_STR="synthetic-production-marker", TF_VAR_authentik_token="marker",
                       TF_VAR_grafana_token="marker")
            result = subprocess.run([str(WRAPPER), "--test-fixture-dir", directory, "--", "plan"],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.splitlines(), ["-chdir=" + directory, "plan"])
            for args in [[], ["--refresh-generated-secrets", "--", "plan"]]:
                result = subprocess.run([str(WRAPPER), "--test-fixture-dir", directory, *args],
                                        env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)

    def test_large_vault_extraction_reaches_init_without_sigpipe(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "env").mkdir()
            (home / "env/grafana.env").write_text("GRAFANA_SERVICE_TOKEN=synthetic-grafana\n")
            binary = home / "bin"
            binary.mkdir()
            vault = binary / "ansible-vault"
            vault.write_text(
                '#!/usr/bin/env python3\n'
                'print("authentik_api_token: synthetic-authentik")\n'
                'print("authentik_postgresql_password: synthetic-postgres")\n'
                'print("# filler " + "x" * 1048576)\n'
                'print("authentik_postgresql_password: duplicate-must-not-win")\n'
            )
            vault.chmod(0o700)
            tofu = binary / "tofu"
            tofu.write_text(
                '#!/usr/bin/env python3\n'
                'import os, sys\n'
                'assert sys.argv[2:] == ["init", "-reconfigure", "-upgrade"]\n'
                'assert os.environ["TF_VAR_authentik_token"] == "synthetic-authentik"\n'
                'assert os.environ["TF_VAR_grafana_token"] == "synthetic-grafana"\n'
                'assert os.environ["PG_CONN_STR"] == '
                '"postgres://terraform:synthetic-postgres@10.229.10.2:5433/terraform_state?sslmode=disable"\n'
                'print("reached-mocked-init")\n'
                'sys.exit(73)\n'
            )
            tofu.chmod(0o700)
            env = {"HOME": str(home), "PATH": str(binary) + os.pathsep + os.environ["PATH"]}
            result = subprocess.run([str(WRAPPER), "--refresh-generated-secrets"],
                                    env=env, capture_output=True, text=True, timeout=10)
            # The sentinel stops before outputs or any generated-secret writes.
            self.assertEqual(result.returncode, 73)
            self.assertEqual(result.stdout.strip(), "")
            self.assertEqual(result.stderr.strip(), "reached-mocked-init")

    def test_production_directory_cannot_be_used_as_a_fixture(self):
        result = subprocess.run([str(WRAPPER), "--test-fixture-dir", str(ROOT / "terraform"), "--", "plan"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("terraform/.passkey-test-*", result.stderr)

    def test_production_symlink_cannot_escape_fixture_prefix(self):
        with tempfile.TemporaryDirectory(prefix=".passkey-test-", dir=ROOT / "terraform") as directory:
            link = Path(directory) / "escape"
            link.symlink_to(ROOT / "terraform", target_is_directory=True)
            result = subprocess.run([str(WRAPPER), "--test-fixture-dir", str(link), "--", "plan"],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
