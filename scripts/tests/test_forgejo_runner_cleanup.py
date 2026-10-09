"""Non-sensitive transient cleanup boundary fixtures."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "src/roles/nixos/files/etc/nixos/modules/forgejo-runner-cleanup.py"
spec = importlib.util.spec_from_file_location("runner_cleanup", SCRIPT)
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


class CleanupTests(unittest.TestCase):
    def test_only_transient_children_removed(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            transient = base / "transient"
            for name in ("workspace", "cache"):
                (transient / name / "nested").mkdir(parents=True)
                (transient / name / "nested/job-output").write_text("fixture")
            for name in ("forgejo", "control", "runtime"):
                (base / name).mkdir()
                (base / name / "keep").write_text("retain")
                (transient / "workspace" / name).symlink_to(base / name, target_is_directory=True)
            cleanup.clean(transient)
            cleanup.clean(transient)  # Repeat is idempotent.
            for name in ("workspace", "cache"):
                self.assertEqual(list((transient / name).iterdir()), [])
            for name in ("forgejo", "control", "runtime"):
                self.assertEqual((base / name / "keep").read_text(), "retain")

    def test_symlink_root_or_child_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            (base / "data").mkdir()
            (base / "data/keep").write_text("retain")
            (base / "alias").symlink_to(base / "data", target_is_directory=True)
            with self.assertRaises(OSError):
                cleanup.clean(base / "alias")
            (base / "transient").mkdir()
            (base / "transient/workspace").symlink_to(base / "data", target_is_directory=True)
            with self.assertRaises(OSError):
                cleanup.clean(base / "transient")
            self.assertEqual((base / "data/keep").read_text(), "retain")
