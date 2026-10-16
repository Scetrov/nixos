"""Offline setup-contract tests; these do not execute SQL or touch a database."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "src/roles/nixos/files/etc/nixos/modules/miniflux-dbsetup.py"
SPEC = importlib.util.spec_from_file_location("miniflux_dbsetup", SCRIPT)
assert SPEC and SPEC.loader
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)


class DatabaseSetupTests(unittest.TestCase):
    def test_password_uses_environment_not_arguments_or_sql(self):
        password = "fixture'\\\"; DROP DATABASE unrelated; --"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "password"
            path.write_text(password)
            with patch.object(setup.subprocess, "run") as run:
                run.return_value.returncode = 0
                setup.reconcile(path)
            self.assertEqual(run.call_count, 2)
            call = run.call_args
            self.assertNotIn(password, " ".join(call.args[0]))
            self.assertNotIn(password, call.kwargs["input"])
            self.assertEqual(call.kwargs["env"]["MINIFLUX_DB_PASSWORD"], password)
            self.assertIn("PASSWORD :'password'", call.kwargs["input"])
            self.assertIn("--env", call.args[0])
            self.assertTrue(call.kwargs["capture_output"])
            self.assertTrue(call.kwargs["check"])
            self.assertEqual(call.kwargs["timeout"], 60)

    def test_ready_retry_is_bounded_and_reconciliation_runs_after_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "password"
            path.write_text("fixture-password")
            with patch.object(setup.subprocess, "run") as run, patch.object(setup.time, "sleep") as sleep:
                run.side_effect = [subprocess.CompletedProcess([], 1), subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 0)]
                setup.reconcile(path, attempts=2)
                self.assertEqual(run.call_count, 3)
                sleep.assert_called_once_with(2)

    def test_outage_never_runs_sql(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "password"
            path.write_text("fixture-password")
            with patch.object(setup.subprocess, "run") as run, patch.object(setup.time, "sleep"):
                run.return_value.returncode = 1
                with self.assertRaisesRegex(RuntimeError, "deadline"):
                    setup.reconcile(path, attempts=2)
                self.assertEqual(run.call_count, 2)
                for call in run.call_args_list:
                    self.assertNotIn("psql", call.args[0])

    def test_invalid_password_fails_before_container_access(self):
        for password in ("", "invalid_placeholder", "fixture\x00password"):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "password"
                path.write_text(password)
                with patch.object(setup.subprocess, "run") as run:
                    with self.assertRaises(ValueError):
                        setup.reconcile(path)
                    run.assert_not_called()

    def test_sql_is_non_destructive_and_restricts_privileges(self):
        for statement in ("DROP DATABASE", "DROP ROLE", "DROP SCHEMA", "TRUNCATE", "DELETE FROM"):
            self.assertNotIn(statement, setup.SQL.upper())
        self.assertIn("WHERE NOT EXISTS", setup.SQL)
        self.assertIn("NOSUPERUSER NOCREATEDB NOCREATEROLE", setup.SQL)
        self.assertIn("NOREPLICATION NOBYPASSRLS", setup.SQL)
        self.assertIn("REVOKE ALL ON DATABASE miniflux FROM PUBLIC", setup.SQL)
        self.assertIn("REVOKE ALL ON SCHEMA public FROM PUBLIC", setup.SQL)
        self.assertIn("Unexpected Miniflux database owner", setup.SQL)
        self.assertIn("Unexpected Miniflux role membership", setup.SQL)
        self.assertLess(setup.SQL.index("SET log_statement"), setup.SQL.index("PASSWORD :'password'"))
        self.assertLess(setup.SQL.index("SET log_min_error_statement"), setup.SQL.index("PASSWORD :'password'"))

    def test_failure_diagnostic_cannot_disclose_subprocess_output(self):
        stderr = io.StringIO()
        failure = subprocess.CalledProcessError(1, ["psql"], output="secret-fixture", stderr="secret-fixture")
        with patch.dict(os.environ, {"CREDENTIALS_DIRECTORY": "/fixture"}), patch.object(setup, "reconcile", side_effect=failure), contextlib.redirect_stderr(stderr):
            self.assertEqual(setup.main(), 1)
        self.assertNotIn("secret-fixture", stderr.getvalue())
        self.assertIn("application startup blocked", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
