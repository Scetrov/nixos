"""Boundary/failure tests for disposable daemon fixture storage cleanup."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.tests.test_forgejo_runner_daemon import cleanup_runtime


class FixtureCleanupTests(unittest.TestCase):
    def runtime(self, root):
        return ["podman", "--cgroup-manager=systemd", "--root", str(root / "storage"),
                "--runroot", str(root / "run")]

    def test_cleanup_is_graph_scoped_and_removes_image_storage(self):
        with tempfile.TemporaryDirectory(prefix="forgejo-daemon-fixture-") as directory:
            root = Path(directory)
            runtime = self.runtime(root)
            with patch("scripts.tests.test_forgejo_runner_daemon.subprocess.run") as run:
                run.return_value = subprocess.CompletedProcess([], 0)
                cleanup_runtime(root, runtime, {})
                calls = [call.args[0] for call in run.call_args_list]
                self.assertEqual(len(calls), 3)
                self.assertTrue(all(args[:len(runtime)] == runtime for args in calls))
                self.assertEqual(calls[1][len(runtime):], ["rmi", "--all", "--force"])
                self.assertEqual(calls[2][len(runtime)], "unshare")
                self.assertEqual(calls[2][-1], str(root))
                self.assertTrue(all("reset" not in args for args in calls))

    def test_rejects_shared_graph_before_any_command(self):
        with tempfile.TemporaryDirectory(prefix="forgejo-daemon-fixture-") as directory:
            root = Path(directory)
            with patch("scripts.tests.test_forgejo_runner_daemon.subprocess.run") as run:
                with self.assertRaises(ValueError):
                    cleanup_runtime(root, ["podman"], {})
                run.assert_not_called()

    def test_cleanup_failure_is_not_ignored(self):
        with tempfile.TemporaryDirectory(prefix="forgejo-daemon-fixture-") as directory:
            root = Path(directory)
            with patch("scripts.tests.test_forgejo_runner_daemon.subprocess.run") as run:
                run.return_value = subprocess.CompletedProcess([], 125)
                with self.assertRaisesRegex(RuntimeError, "cleanup failed"):
                    cleanup_runtime(root, self.runtime(root), {})
                self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
