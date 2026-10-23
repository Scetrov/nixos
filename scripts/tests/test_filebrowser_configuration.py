"""Read-only Nix evaluation and private runtime configuration regression tests."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from scripts.filebrowser_runtime import runtime_config

ROOT = Path(__file__).resolve().parents[2]
IMAGE = "ghcr.io/gtsteffaniak/filebrowser@sha256:989e2dc6c491bda3c8bb82b27cd7798924ff3025cabdcad2444eb42f774836f6"


class RuntimeTests(unittest.TestCase):
    def test_runtime_has_only_explicit_private_sources_and_oidc(self):
        records = json.loads((ROOT / "src/filebrowser-enrollments.json").read_text())
        config = runtime_config(records, "synthetic-id", "synthetic-secret", 8092)
        self.assertEqual(config["http"]["externalUrl"], "https://files.net.scetrov.live")
        self.assertTrue(config["http"]["disableWebDAV"])
        self.assertTrue(config["http"]["trustProxyHeaders"])
        self.assertFalse(config["auth"]["methods"]["password"]["enabled"])
        self.assertFalse(config["auth"]["methods"]["password"]["signup"])
        self.assertEqual(config["auth"]["methods"]["oidc"]["adminGroup"], "")
        self.assertFalse(any(config["userDefaults"]["account"]["permissions"].values()))
        self.assertTrue(config["server"]["database"]["activity"]["disabled"])
        self.assertEqual(config["server"]["filesystem"]["createFilePermission"], "660")
        for entry, source in zip(records, config["server"]["sources"]):
            self.assertEqual(source["path"], "/documents/" + entry["unix_username"])
            self.assertEqual(source["config"], {"private": True, "defaultEnabled": False})

    def test_machine_auth_is_explicit_and_separate_from_ordinary_oidc(self):
        config = runtime_config([], "fixture", "fixture", 8092, "-----BEGIN PUBLIC KEY-----\nfixture\n-----END PUBLIC KEY-----")
        machine = config["auth"]["methods"]["jwt"]
        self.assertEqual(machine["algorithm"], "RS256")
        self.assertEqual(machine["userGroups"], ["filebrowser-reconciler"])
        self.assertEqual(machine["header"], "X-Filebrowser-Admin-Assertion")
        self.assertEqual(config["auth"]["methods"]["oidc"]["adminGroup"], "")
        with self.assertRaises(ValueError):
            runtime_config([], "fixture", "fixture", 8092, "-----BEGIN PRIVATE KEY-----")


@unittest.skipUnless(shutil.which("nix-instantiate"), "Nix evaluation requires nix-instantiate")
class NixConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.configs = {}
        for enabled in (True, False):
            result = subprocess.run(["nix-instantiate", "--eval", "--strict", "--json", "tests/filebrowser-eval.nix", "--arg", "enable", str(enabled).lower()], cwd=ROOT, capture_output=True, text=True, timeout=120)
            if result.returncode:
                raise AssertionError(result.stderr[-4000:])
            cls.configs[enabled] = json.loads(result.stdout)

    def test_pinned_nonroot_runtime_mounts_only_documents_and_private_state(self):
        cfg = self.configs[True]
        self.assertEqual(cfg["assertions"], [])
        container = cfg["containers"]["filebrowser"]
        self.assertEqual(container["image"], IMAGE)
        self.assertEqual(container["user"], "61990:61990")
        self.assertEqual(container["ports"], ["127.0.0.1:8092:8080"])
        self.assertIn("--userns=host", container["extraOptions"])
        self.assertIn("--cap-drop=ALL", container["extraOptions"])
        self.assertIn("--read-only", container["extraOptions"])
        self.assertEqual(len(container["volumes"]), 5)
        self.assertFalse(any(volume.startswith("/home") for volume in container["volumes"]))
        self.assertIn("filebrowser_runtime.py", cfg["preparation"])
        self.assertEqual(len(cfg["credentials"]), 3)

    def test_route_is_readiness_gated_and_strips_machine_credentials(self):
        cfg = self.configs[True]
        route = cfg["caddyRoute"]
        self.assertIn("@ready file", route)
        self.assertIn("root /run/filebrowser", route)
        self.assertIn("try_files ready", route)
        self.assertIn("header_up -X-Filebrowser-Admin-Assertion", route)
        self.assertIn("respond 404", route)
        self.assertNotIn("handle /public/*", route)
        self.assertIn("/public/share* /public/api*", route)
        self.assertIn("503", route)
        self.assertIn("files.net.scetrov.live", cfg["aliases"])

    def test_health_alert_and_logs_use_existing_observability(self):
        cfg = self.configs[True]
        jobs = [job for job in cfg["scrapeConfigs"] if job["job_name"] == "filebrowser-edge"]
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["params"]["module"], ["filebrowser_https"])
        self.assertEqual(jobs[0]["static_configs"][0]["targets"], ["https://127.0.0.1/health"])
        self.assertIn("(podman-filebrowser|filebrowser-reconcile)", cfg["journalConfig"])
        rule = cfg["alerting"]["groups"][0]["rules"][0]
        self.assertEqual(rule["uid"], "filebrowser-unavailable")
        self.assertEqual(rule["for"], "5m")
        self.assertEqual(rule["noDataState"], "Alerting")
        self.assertIn("absent(probe_success", rule["data"][0]["model"]["expr"])
        self.assertEqual(self.configs[False]["alerting"]["deleteRules"][0]["uid"], "filebrowser-unavailable")
        self.assertNotIn("(podman-filebrowser|filebrowser-reconcile)", self.configs[False]["journalConfig"])

    def test_disabling_removes_runtime_and_credentials(self):
        cfg = self.configs[False]
        self.assertNotIn("filebrowser", cfg["containers"])
        self.assertNotIn("podman-filebrowser", cfg["units"])
        self.assertFalse(any(name.startswith("filebrowser") for name in cfg["secrets"]))


class SecretRuleTests(unittest.TestCase):
    def test_every_rendered_filebrowser_secret_has_a_habiki_rule(self):
        rendered = (ROOT / "src/roles/secrets/tasks/filebrowser.yml").read_text()
        rules = (ROOT / "src/roles/secrets/files/secrets/secrets.nix").read_text()
        names = re.findall(r"'name': '([^']+)'", rendered)
        self.assertEqual(len(names), 5)
        for name in names:
            self.assertIn(f'"{name}.age".publicKeys = users ++ [ habiki ];', rules)


class DeploymentBoundaryTests(unittest.TestCase):
    def test_tag_guard_accepts_only_the_focused_tuple(self):
        source = (ROOT / "src/filebrowser.yml").read_text()
        task = source.split("  pre_tasks:\n", 1)[1].split("    - name: Close the Filebrowser readiness gate", 1)[0]
        play = "- hosts: habiki\n  connection: local\n  gather_facts: false\n  tags: [filebrowser]\n  tasks:\n" + task
        with tempfile.TemporaryDirectory(prefix="filebrowser-tag-regression-") as directory:
            directory = Path(directory)
            (directory / "ansible.cfg").write_text("[defaults]\n")
            playbook = directory / "boundary.yml"
            playbook.write_text(play)
            environment = {**os.environ, "ANSIBLE_CONFIG": str(directory / "ansible.cfg")}
            for tags, expected in (("filebrowser", 0), ("filebrowser,nixos", 2), ("all", 2)):
                result = subprocess.run(["ansible-playbook", "-i", "habiki,", str(playbook), "--limit", "habiki", "--tags", tags], cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, expected, tags + "\n" + (result.stdout + result.stderr)[-2000:])

    def test_wrapper_rejects_widened_targets_or_skipped_credentials(self):
        for args in (["--tags", "filebrowser"], ["--limit", "habiki", "--tags", "filebrowser,nixos"], ["--limit", "habiki", "--tags", "filebrowser", "--skip-generated-refresh"], ["--limit", "habiki", "--tags", "filebrowser", "--", "--limit", "all"]):
            result = subprocess.run(["bash", "scripts/play.sh", *args], cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Error:", result.stderr)

    def test_deployment_waits_for_scope_reconciliation(self):
        play = (ROOT / "src/filebrowser.yml").read_text()
        self.assertIn("[systemctl, start, --wait, filebrowser-reconcile.service]", play)
        self.assertNotIn("name: filebrowser-reconcile.service", play)


if __name__ == "__main__":
    unittest.main()
