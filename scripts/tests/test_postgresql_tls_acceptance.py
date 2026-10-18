"""Static safety/structure checks for the explicitly opt-in live renewal play."""
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def walk(tasks):
    for task in tasks:
        yield task
        for key in ("block", "always", "rescue"):
            yield from walk(task.get(key, []))


class RenewalAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.play, = yaml.safe_load((ROOT / "src/postgresql-tls-acceptance.yml").read_text())
        self.tasks = list(walk(self.play["tasks"]))

    def test_explicit_approval_host_scope_and_no_reboot(self):
        self.assertEqual(self.play["hosts"], "habiki")
        self.assertFalse(self.play["gather_facts"])
        guards = self.tasks[0]["ansible.builtin.assert"]["that"]
        self.assertIn("postgresql_tls_acceptance_renew | default(false) | bool", guards)
        self.assertIn("not ansible_check_mode", guards)
        self.assertFalse(any("ansible.builtin.reboot" in task for task in self.tasks))

    def test_single_invocation_preserves_postrun_and_runtime_only_override(self):
        starts = [task for task in self.tasks
                  if task.get("ansible.builtin.systemd_service", {}).get("state") == "started"]
        self.assertEqual(len(starts), 1)
        self.assertEqual(starts[0]["ansible.builtin.systemd_service"]["name"], "{{ renewal_unit }}")
        self.assertTrue(starts[0]["no_log"])
        override, = [task["ansible.builtin.copy"] for task in self.tasks if "ansible.builtin.copy" in task]
        self.assertIn("Restart=no", override["content"])
        self.assertIn("TimeoutStartSec=20min", override["content"])
        self.assertNotIn("ExecStartPost", override["content"])
        self.assertNotIn("LoadCredential", override["content"])
        self.assertTrue(self.play["vars"]["dropin_path"].startswith("/run/systemd/system/"))
        self.assertTrue(self.play["vars"]["runtime_dir"].startswith("/run/"))

    def test_cleanup_runs_on_failure_and_reports_its_own_failures(self):
        block, = [task for task in self.play["tasks"] if "block" in task]
        cleanup = block["always"]
        self.assertEqual(len([t for t in cleanup if t.get("ignore_errors")]), 5)
        checks = cleanup[-1]["ansible.builtin.assert"]["that"]
        self.assertEqual(len(checks), 5)
        text = str(cleanup)
        self.assertIn("timer_before.stdout", text)
        self.assertIn("runtime_claim.rc", text)
        self.assertIn("acceptance_dropin is defined", text)

    def test_embedded_python_compiles_and_guards_exact_script_transformation(self):
        compile(self.play["vars"]["acceptance_probe"], "probe", "exec")
        sources = []
        for task in self.tasks:
            argv = task.get("ansible.builtin.command", {}).get("argv", [])
            if argv[:2] == ["python3", "-c"] and not argv[2].startswith("{{"):
                compile(argv[2], task["name"], "exec")
                sources.append(argv[2])
        source = "\n".join(sources)
        self.assertIn("assert source.count(old)==1 and new not in source", source)
        self.assertIn("assert modified.replace(new,old)==source", source)
        self.assertIn("renew --no-random-sleep --days 90", source)
        self.assertIn("path.open('x')", source)
        self.assertIn("assert state=='inactive'", source)
        self.assertIn("not pathlib.Path(directory).exists()", source)


class RebootAcceptanceTests(unittest.TestCase):
    def test_explicit_recovery_approval_expected_certificate_and_bounded_reboot(self):
        play, = yaml.safe_load((ROOT / "src/postgresql-tls-reboot.yml").read_text())
        self.assertEqual(play["hosts"], "habiki")
        guards = play["tasks"][0]["ansible.builtin.assert"]["that"]
        self.assertIn("postgresql_tls_acceptance_reboot | default(false) | bool", guards)
        self.assertIn("postgresql_tls_recovery_confirmed | default(false) | bool", guards)
        self.assertIn("postgresql_tls_expected_fingerprint is defined", guards)
        compile(play["vars"]["boot_probe"], "boot probe", "exec")
        reboots = [t["ansible.builtin.reboot"] for t in play["tasks"] if "ansible.builtin.reboot" in t]
        self.assertEqual(len(reboots), 1)
        self.assertLessEqual(reboots[0]["reboot_timeout"], 600)
        self.assertEqual(reboots[0]["search_paths"], ["/run/current-system/sw/bin"])
        preflights = [t.get("ansible.builtin.command", {}).get("argv", []) for t in play["tasks"]]
        self.assertIn(["test", "-x", "/run/current-system/sw/bin/shutdown"], preflights)
        probe = play["vars"]["boot_probe"]
        self.assertIn("0 < prepared <= database_started", probe)
        self.assertIn("assert key_mode=='0:70 640'", probe)
        self.assertIn("not pathlib.Path(path).exists()", probe)


if __name__ == "__main__":
    unittest.main()
