"""Focused scheduling deployment and freshness regression checks."""

from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("scheduling_probe", ROOT / "scripts/tests/check_hermes_scheduling.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class HermesSchedulingTests(unittest.TestCase):
    def test_habiki_uses_pinned_release_and_distinct_source_not_home(self):
        device = (ROOT / "src/roles/nixos/files/device-configuration/habiki.nix").read_text()
        self.assertIn('agentImage = "docker.io/nousresearch/hermes-agent:v2026.9.24@sha256:fca358f12efd65bfaaca05884166f15c0e2788375ca30d77061ac1ebc96452b7";', device)
        self.assertIn('agentSourceVolume = "hermes-agent-src-v2026-9-24";', device)
        self.assertNotIn("homeVolume =", device)
        self.assertIn("enableDashboard = false;", device)
        self.assertIn("rootless = false;", device)

    def test_hostport_migration_is_guarded_exact_and_checks_the_host_path(self):
        play, = yaml.safe_load((ROOT / "src/hermes-runtime.yml").read_text())
        tasks = {task["name"]: task for task in play["tasks"]}
        migration = tasks["Remove only the retired Hermes port forwarding rules"]
        self.assertIn("hermes_retired_container.rc == 1", migration["when"])
        self.assertIn("!= '10.89.1.9'", migration["when"][1])
        rules = [task["ansible.builtin.iptables"] for task in migration["block"]]
        self.assertEqual(len(rules), 2)
        for rule in rules:
            self.assertEqual(rule["state"], "absent")
            self.assertEqual(rule["table"], "nat")
            self.assertEqual(rule["destination_port"], "8787")
            self.assertNotIn("flush", rule)
        self.assertEqual(rules[0]["destination"], "127.0.0.1/32")
        self.assertEqual(rules[0]["to_destination"], "10.89.1.9:8787")
        self.assertIn("9496cc5c73f1fa5e", rules[1]["comment"])
        readiness = tasks["Verify Hermes is reachable through the host loopback publication"]
        self.assertEqual(readiness["ansible.builtin.uri"]["url"], "http://127.0.0.1:8787/")
        self.assertFalse(readiness["ansible.builtin.uri"]["use_proxy"])
        self.assertEqual(readiness["ansible.builtin.uri"]["status_code"], 200)

    def test_freshness_distinguishes_empty_healthy_from_stale_and_stopped(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            path = home / "gateway_state.json"
            now = datetime.now(timezone.utc)
            for state, age, healthy in [("running", 10, True), ("running", 180, False), ("stopped", 0, False)]:
                with self.subTest(state=state, age=age):
                    status = {"gateway_state": state, "updated_at": (now - timedelta(seconds=age)).isoformat()}
                    path.write_text(json.dumps(status))
                    if healthy:
                        self.assertEqual(probe.fresh_status(home), status["updated_at"])
                    else:
                        with self.assertRaises(AssertionError):
                            probe.fresh_status(home)


if __name__ == "__main__":
    unittest.main()
