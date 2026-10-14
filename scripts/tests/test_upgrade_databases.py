"""Run normal unit tests, or RUN_CONTAINER_TESTS=1 for the real PG16/17 restore."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "upgrade_databases", ROOT / "src/roles/nixos/files/upgrade_databases.py"
)
upgrade = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(upgrade)
PG16 = "docker.io/library/postgres:16-alpine@sha256:4941ef97aaa2633ce9808f7766f8b8d746dd039ce8c51ca6da185c3dc63ab579"


class MigrationTests(unittest.TestCase):
    def test_failed_restore_leaves_all_originals_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entries = {}
            for name, user in upgrade.DATABASES.items():
                data = root / name
                data.mkdir()
                (data / "PG_VERSION").write_text("16\n")
                entries[name] = {"data": str(data), "user": user}
            redis = root / "redis"
            redis.mkdir()
            (redis / "dump.rdb").write_bytes(b"fixture")

            def fake_run(*args, **kwargs):
                if args[0] == "du":
                    return b"100 data\n"
                if args[0] == "cp":
                    import shutil
                    shutil.copytree(args[-2], args[-1])
                if "pg_dumpall" in args:
                    kwargs["stdout"].write(b"a fixture dump\n")
                if "psql" in args:
                    return b"postgres\n"
                return b""

            backup = root / "backup"
            with patch.object(upgrade, "inventory", return_value=entries), \
                    patch.object(upgrade, "inspect", return_value={"Mounts": [
                        {"Destination": "/data", "Source": str(redis)}
                    ]}), patch.object(upgrade, "stop_services"), \
                    patch.object(upgrade, "run", side_effect=fake_run), \
                    patch.object(upgrade, "restore", side_effect=["postgres\n", RuntimeError("bad dump")]):
                with self.assertRaises(RuntimeError):
                    upgrade.migrate(backup)
            for entry in entries.values():
                self.assertEqual((Path(entry["data"]) / "PG_VERSION").read_text(), "16\n")
            self.assertTrue((backup / "dump.rdb").exists())

    def test_rollback_preserves_failed_pg17_and_restores_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data"
            data.mkdir()
            (data / "PG_VERSION").write_text("17\n")
            original = root / "data.pg16-before-upgrade"
            original.mkdir()
            (original / "PG_VERSION").write_text("16\n")
            manifest = {"generation": "/nix/store/fixture-old-generation",
                        "databases": {"oncall-postgres": {"data": str(data)}},
                        "installed": ["oncall-postgres"]}
            upgrade.save_manifest(root, manifest)
            with patch.object(upgrade, "stop_services"), \
                    patch.object(upgrade, "run", return_value=b"loaded\n") as commands:
                upgrade.rollback(root)
            self.assertEqual((data / "PG_VERSION").read_text(), "16\n")
            failed = list(root.glob("data.failed-pg17-*"))
            self.assertEqual(len(failed), 1)
            self.assertEqual((failed[0] / "PG_VERSION").read_text(), "17\n")
            commands.assert_any_call("/nix/store/fixture-old-generation/bin/switch-to-configuration", "switch")

    def test_maintenance_wrapper_requires_exact_host(self):
        result = subprocess.run([str(ROOT / "scripts/play.sh"), "--tags", "database-upgrade"],
                                capture_output=True, text=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires --limit habiki", result.stderr)

    def test_inventory_refuses_pg17(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            (data / "PG_VERSION").write_text("17\n")
            with patch.object(upgrade, "inspect", return_value={"Mounts": [
                {"Destination": "/var/lib/postgresql/data", "Source": directory}
            ]}):
                with self.assertRaises(RuntimeError):
                    upgrade.inventory()

    def test_run_can_stream_dump_to_file(self):
        with tempfile.TemporaryFile() as output:
            upgrade.run("printf", "a database dump", stdout=output)
            output.seek(0)
            self.assertEqual(output.read(), b"a database dump")

    def test_ready_timeout_is_bounded(self):
        with patch.object(upgrade, "run", side_effect=subprocess.CalledProcessError(1, "pg_isready")), \
                patch.object(upgrade.time, "sleep"):
            with self.assertRaises(RuntimeError):
                upgrade.wait_ready("fixture", "oncall")

    def test_bad_restore_removes_container_and_keeps_dump(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dump = root / "dump.sql"
            dump.write_text("CREATE ROLE oncall;\nNOT VALID SQL;\n")
            calls = []

            def fake_run(*args, **kwargs):
                calls.append(args)
                if "psql" in args:
                    self.assertNotIn(b"CREATE ROLE oncall;", kwargs["stdin"].read())
                    raise subprocess.CalledProcessError(1, "psql")
                return b""

            with patch.object(upgrade, "run", side_effect=fake_run):
                with self.assertRaises(subprocess.CalledProcessError):
                    upgrade.restore(dump, root / "new-data", "oncall", "fixture")
            self.assertIn(("podman", "stop", "fixture"), calls)
            self.assertIn(("podman", "rm", "fixture"), calls)
            self.assertTrue(dump.exists())
            self.assertFalse(dump.with_suffix(".restore.sql").exists())


@unittest.skipUnless(os.environ.get("RUN_CONTAINER_TESTS") == "1", "explicit local container test")
class RestoreIntegration(unittest.TestCase):
    def test_pg16_to_pg17_preserves_data_and_globals(self):
        root = Path(tempfile.mkdtemp(prefix="homelab-pg-test-"))
        suffix = str(os.getpid())
        old, new = f"upgrade-test16-{suffix}", f"upgrade-test17-{suffix}"
        try:
            for image in [PG16, upgrade.PG17]:
                upgrade.run("podman", "pull", image)
            env = dict(os.environ, POSTGRES_PASSWORD="local-fixture-only")
            upgrade.run("podman", "run", "-d", "--name", old, "--network=none",
                        "--env", "POSTGRES_PASSWORD", "--env", "POSTGRES_USER=oncall",
                        "--env", "POSTGRES_DB=postgres", PG16, env=env)
            upgrade.wait_ready(old, "oncall")
            upgrade.run("podman", "exec", old, "psql", "-U", "oncall", "-d", "postgres",
                        "-v", "ON_ERROR_STOP=1", "-c", "CREATE ROLE terraform LOGIN")
            for database in ["oncall", "terraform_state"]:
                upgrade.run("podman", "exec", old, "createdb", "-U", "oncall", database)
                upgrade.run("podman", "exec", old, "psql", "-U", "oncall", "-d", database,
                            "-v", "ON_ERROR_STOP=1", "-c",
                            "CREATE TABLE fixture(id int PRIMARY KEY); INSERT INTO fixture VALUES (42)")
            dump = root / "dump.sql"
            with dump.open("wb") as output:
                upgrade.run("podman", "exec", old, "pg_dumpall", "-U", "oncall", stdout=output)
            databases = upgrade.restore(dump, root / "pg17", "oncall", new)
            self.assertEqual(databases, "oncall\npostgres\nterraform_state\n")
            # Reopen the verified restored data with the same pinned image.
            upgrade.run("podman", "run", "-d", "--name", new, "--network=none",
                        "-v", f"{root / 'pg17'}:/var/lib/postgresql/data", upgrade.PG17)
            upgrade.wait_ready(new, "oncall")
            for database in ["oncall", "terraform_state"]:
                value = upgrade.run("podman", "exec", new, "psql", "-U", "oncall", "-d", database,
                                    "-XAt", "-c", "SELECT id FROM fixture")
                self.assertEqual(value, b"42\n")
            role = upgrade.run("podman", "exec", new, "psql", "-U", "oncall", "-d", "postgres",
                               "-XAt", "-c", "SELECT rolcanlogin FROM pg_roles WHERE rolname='terraform'")
            self.assertEqual(role, b"t\n")
        finally:
            for name in [old, new]:
                subprocess.run(["podman", "rm", "-f", "-v", name], capture_output=True, check=False)
            subprocess.run(["podman", "unshare", "rm", "-rf", str(root)], check=True)


if __name__ == "__main__":
    unittest.main()
