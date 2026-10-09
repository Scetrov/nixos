"""Reset regression tests: fake only the container CLI, run the real reset script."""
import concurrent.futures
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RESET = ROOT / "src/roles/nixos/files/etc/nixos/modules/frontier-indexer-reset.sh"


class ResetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.marker = self.directory / "generation"
        self.envfile = self.directory / "indexer.env"
        self.calls = self.directory / "sql-calls"
        self.envfile.write_text(
            "DB_HOST=test\nDB_PORT=5432\nDB_NAME=postgres\nDB_USER=postgres\n"
            "DB_PASSWORD=test-only-password\nDB_SCHEMA=indexer\n"
        )
        fake = self.directory / "podman"
        fake.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\n"
            'if [ "$1" = ps ]; then\n'
            '  if [ "${WRITER_RUNNING:-0}" = 1 ]; then echo frontier-indexer; fi\n'
            "  exit 0\nfi\n"
            'if [ "${2:-}" != -i ]; then echo "SQL stdin not forwarded" >&2; exit 1; fi\n'
            'cat >> "$SQL_CALLS"\n'
            'sleep "${RESET_DELAY:-0}"\n'
            'if [ "${RESET_FAIL:-0}" = 1 ]; then exit 1; fi\n'
            'if [ "${MARKER_FAIL:-0}" = 1 ]; then chmod 0500 "$MARKER_DIR"; fi\n'
        )
        fake.chmod(0o755)
        self.environment = dict(
            os.environ,
            PATH=f"{self.directory}:{os.environ['PATH']}",
            SQL_CALLS=str(self.calls),
            MARKER_DIR=str(self.directory),
        )
        self.addCleanup(lambda: self.directory.chmod(0o700))

    def reset(self, generation="7", **environment):
        return subprocess.run(
            ["bash", str(RESET), str(self.envfile), str(self.marker), generation,
             "test-image", "test-network"],
            env=dict(self.environment, **environment),
            text=True, capture_output=True, timeout=15,
        )

    def assert_no_sql(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.calls.exists())
        self.assertNotIn("test-only-password", result.stdout + result.stderr)

    def test_missing_marker_resets_and_equal_generation_preserves(self):
        result = self.reset()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.marker.read_text(), "7")
        self.assertEqual(self.marker.stat().st_mode & 0o777, 0o640)
        sql = self.calls.read_text()
        self.assertIn("BEGIN;", sql)
        self.assertIn("COMMIT;", sql)
        self.assertEqual(self.reset().returncode, 0)
        self.assertEqual(self.calls.read_text(), sql)
        self.assertFalse(list(self.directory.glob("generation.*[0-9]")))

    def test_older_marker_advances(self):
        self.marker.write_text("6")
        self.assertEqual(self.reset().returncode, 0)
        self.assertEqual(self.marker.read_text(), "7")

    def test_stale_request_leaves_marker_unchanged(self):
        self.marker.write_text("8")
        self.assert_no_sql(self.reset())
        self.assertEqual(self.marker.read_text(), "8")

    def test_invalid_markers_fail_closed(self):
        for marker in ["", "garbage", "-1", "07", "7\n8", "9223372036854775808"]:
            with self.subTest(marker=marker):
                self.marker.write_text(marker)
                self.assert_no_sql(self.reset())
                self.assertEqual(self.marker.read_text(), marker)

    def test_invalid_configured_generation(self):
        for generation in ["-1", "garbage", "07", "9223372036854775808"]:
            with self.subTest(generation=generation):
                self.assert_no_sql(self.reset(generation))

    def test_null_generation_only_allowed_without_marker(self):
        self.assertEqual(self.reset("").returncode, 0)
        self.assertFalse(self.calls.exists())
        self.marker.write_text("7")
        self.assert_no_sql(self.reset(""))

    def test_running_writer_blocks_reset(self):
        self.assert_no_sql(self.reset(WRITER_RUNNING="1"))
        self.assertFalse(self.marker.exists())
        self.assertEqual(self.reset(WRITER_RUNNING="0").returncode, 0)

    def test_failed_sql_does_not_publish_marker_and_can_retry(self):
        self.marker.write_text("6")
        self.assertNotEqual(self.reset(RESET_FAIL="1").returncode, 0)
        self.assertEqual(self.marker.read_text(), "6")
        self.assertEqual(self.reset().returncode, 0)
        self.assertEqual(self.marker.read_text(), "7")

    def test_failed_marker_publication_fails_startup(self):
        if os.geteuid() == 0:
            self.skipTest("requires unprivileged permissions")
        self.marker.write_text("6")
        self.assertNotEqual(self.reset(MARKER_FAIL="1").returncode, 0)
        self.directory.chmod(0o700)
        self.assertEqual(self.marker.read_text(), "6")
        self.assertEqual(self.reset().returncode, 0)
        self.assertEqual(self.marker.read_text(), "7")

    def test_concurrent_resets_are_serialized(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.reset(RESET_DELAY="0.2"), range(2)))
        self.assertTrue(all(result.returncode == 0 for result in results))
        self.assertEqual(self.calls.read_text().count("DROP SCHEMA"), 1)
        self.assertEqual(self.marker.read_text(), "7")

    def test_unexpected_schema_refused(self):
        self.envfile.write_text(self.envfile.read_text().replace("DB_SCHEMA=indexer", "DB_SCHEMA=public"))
        self.assert_no_sql(self.reset())


if __name__ == "__main__":
    unittest.main()
