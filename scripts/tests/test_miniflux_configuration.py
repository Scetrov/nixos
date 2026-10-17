"""Evaluate configuration and exercise deployment ordering without infrastructure."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which("nix-instantiate"), "Nix evaluation requires nix-instantiate")
class ConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.configs = {}
        for enabled, grafana in ((True, True), (False, True), (True, False)):
            args = ["nix-instantiate", "--eval", "--strict", "--json"]
            if os.environ.get("NIXPKGS"):
                args += ["-I", "nixpkgs=" + os.environ["NIXPKGS"]]
            args += ["tests/miniflux-eval.nix", "--arg", "enable", str(enabled).lower(),
                     "--arg", "grafanaEnable", str(grafana).lower()]
            result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=120)
            if result.returncode:
                raise AssertionError("Miniflux configuration evaluation failed: " + result.stderr[-4000:])
            cls.configs[enabled, grafana] = json.loads(result.stdout)

    def test_optional_subscription_units_are_explicit_and_hardened(self):
        self.assertEqual(self.configs[True, True]["subscriptionUnits"], {})
        args = ["nix-instantiate", "--eval", "--strict", "--json"]
        if os.environ.get("NIXPKGS"):
            args += ["-I", "nixpkgs=" + os.environ["NIXPKGS"]]
        args += ["tests/miniflux-eval.nix", "--arg", "subscriptionsEnable", "true"]
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        cfg = json.loads(result.stdout)
        self.assertIn("miniflux_subscription_api_token", cfg["secretNames"])
        self.assertEqual(len(cfg["subscriptionUnits"]), 2)
        for name, unit in cfg["subscriptionUnits"].items():
            self.assertEqual(unit["wantedBy"], [])
            self.assertEqual(unit["restartTriggers"], [])
            self.assertFalse(unit["restartIfChanged"])
            self.assertFalse(unit["stopIfChanged"])
            self.assertIn("miniflux.service", unit["requisite"])
            service = unit["config"]
            self.assertEqual(service["Type"], "oneshot")
            self.assertEqual(service["ProtectSystem"], "strict")
            self.assertTrue(service["NoNewPrivileges"])
            self.assertLessEqual(service["TimeoutStartSec"], 2500)
            self.assertEqual(service["IPAddressAllow"], "127.0.0.1/32")
            self.assertIn("api-token:/run/agenix/miniflux_subscription_api_token", service["LoadCredential"])
            self.assertIn("%d/api-token", service["ExecStart"])
            self.assertIn(" plan " if name.endswith("-plan") else " apply ", service["ExecStart"])
        args += ["--arg", "enable", "false"]
        disabled = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(disabled.returncode, 0, disabled.stderr[-4000:])
        self.assertEqual(json.loads(disabled.stdout)["subscriptionUnits"], {})

    def test_native_loopback_runtime_and_credentials(self):
        cfg = self.configs[True, True]
        self.assertTrue(cfg["enabled"])
        self.assertFalse(cfg["localDatabase"])
        env = cfg["environment"]
        self.assertEqual(env["LISTEN_ADDR"], "127.0.0.1:8091")
        self.assertEqual(env["DATABASE_MAX_CONNS"], "5")
        self.assertNotIn("DATABASE_URL", env)
        self.assertEqual(env["DISABLE_LOCAL_AUTH"], "1")
        self.assertEqual(env["CREATE_ADMIN"], "0")
        self.assertEqual(env["RUN_MIGRATIONS"], "1")
        self.assertEqual(len(cfg["credentials"]), 3)
        self.assertIn("miniflux-dbsetup.service", cfg["ordering"]["requires"])
        self.assertIn("miniflux-dbsetup.service", cfg["ordering"]["after"])

    def test_native_api_route_and_public_metrics_denial_without_grafana(self):
        for grafana in (True, False):
            cfg = self.configs[True, grafana]
            self.assertIn("feed.net.scetrov.live", cfg["virtualHosts"])
            self.assertEqual(cfg["caddyCertificate"], "scetrov.live")
            route = cfg["caddyConfig"]
            self.assertIn("handle /metrics*", route)
            self.assertIn("respond 404", route)
            self.assertIn("reverse_proxy 127.0.0.1:8091", route)
            self.assertNotIn("forward_auth", route)
            self.assertNotIn("rewrite", route)
            self.assertLess(route.index("respond 404"), route.index("reverse_proxy"))
        self.assertIsNone(self.configs[True, False]["alerting"])

    def test_dns_scrape_logs_and_routed_sustained_alert(self):
        cfg = self.configs[True, True]
        self.assertIn("feed.net.scetrov.live", cfg["aliases"])
        scrape, = cfg["scrapeConfigs"]
        self.assertEqual(scrape["static_configs"][0]["targets"], ["127.0.0.1:8091"])
        self.assertEqual(scrape["static_configs"][0]["labels"]["service"], "miniflux")
        self.assertIn("miniflux(-dbsetup|-subscriptions(-plan)?)?", cfg["journalConfig"])
        group, = cfg["alerting"]["groups"]
        rule, = group["rules"]
        self.assertEqual(rule["for"], "5m")
        self.assertEqual(rule["labels"]["service"], "miniflux")
        self.assertEqual(rule["data"][0]["datasourceUid"], "mimir")
        self.assertNotIn("notification_settings", rule)  # inherit shared routing
        self.assertIn("absent(", rule["data"][0]["model"]["expr"])

    def test_disabling_removes_runtime_route_scrape_and_deletes_alert(self):
        cfg = self.configs[False, True]
        self.assertFalse(cfg["enabled"])
        self.assertEqual(cfg["serviceNames"], [])
        self.assertEqual(cfg["secretNames"], [])
        self.assertEqual(cfg["scrapeConfigs"], [])
        self.assertNotIn("feed.net.scetrov.live", cfg["virtualHosts"])
        self.assertNotIn("miniflux(-dbsetup|-subscriptions(-plan)?)?", cfg["journalConfig"])
        self.assertEqual(cfg["alerting"]["groups"], [])
        self.assertEqual(cfg["alerting"]["deleteRules"], [{"orgId": 1, "uid": "miniflux-unavailable"}])


class DeploymentTests(unittest.TestCase):
    def run_play(self, args):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            scripts = base / "scripts"
            scripts.mkdir()
            shutil.copyfile(ROOT / "scripts/play.sh", scripts / "play.sh")
            events = base / "events.jsonl"
            stub = f"#!{sys.executable}\nimport json, os, sys\nwith open(os.environ['EVENTS'], 'a') as f: f.write(json.dumps([os.path.basename(sys.argv[0]), *sys.argv[1:]]) + '\\n')\n"
            for path in (scripts / "tofu.sh", scripts / "ansible-playbook"):
                path.write_text(stub)
                path.chmod(0o700)
            env = dict(os.environ, EVENTS=str(events), PATH=str(scripts) + os.pathsep + os.environ["PATH"])
            result = subprocess.run(["bash", str(scripts / "play.sh"), *args], cwd=base,
                                    env=env, capture_output=True, text=True, timeout=10)
            calls = [json.loads(line) for line in events.read_text().splitlines()] if events.exists() else []
            return result, calls

    def test_subscriptions_require_exact_scope_and_do_not_refresh_identity(self):
        for suffix in ([], ["--", "-e", "miniflux_subscriptions_apply=true"],
                       ["--", "--check"], ["--", "--syntax-check"], ["--", "--list-tasks"],
                       ["--", "--list-tags"], ["--", "--list-hosts"]):
            result, calls = self.run_play(["--limit", "habiki", "--tags", "miniflux-subscriptions", *suffix])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][0], "ansible-playbook")
            self.assertIn("src/miniflux-subscriptions.yml", calls[0])
        for args in (["--tags", "miniflux-subscriptions"],
                     ["--limit", "fyne", "--tags", "miniflux-subscriptions"],
                     ["--limit", "habiki", "--tags", "miniflux-subscriptions,nixos"],
                     ["--limit", "habiki", "--tags", "miniflux-subscriptions", "--", "-lfyne"]):
            result, calls = self.run_play(args)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(calls, [])

    def test_optional_token_delivery_is_guarded_and_not_logged(self):
        tasks = yaml.safe_load((ROOT / "src/roles/secrets/tasks/miniflux.yml").read_text())
        optional = [t for t in tasks if "subscription" in t["name"].lower()]
        self.assertEqual(len(optional), 2)
        for task in optional:
            self.assertTrue(task["no_log"])
            self.assertIn("miniflux_subscriptions_enabled | default(false)", task["when"])
        declarations = (ROOT / "src/roles/secrets/files/secrets/secrets.nix").read_text()
        self.assertIn('"miniflux_subscription_api_token.age".publicKeys = users ++ [ habiki ];', declarations)
        copies = yaml.safe_load((ROOT / "src/roles/nixos/tasks/sync.yml").read_text())
        tool_copy, = [t for t in copies if t["name"].startswith("Copy Miniflux subscription")]
        self.assertEqual(tool_copy["when"], "miniflux_enabled | default(false)")
        self.assertEqual([i["source"] for i in tool_copy["loop"]],
                         ["scripts/miniflux_subscriptions.py", "config/miniflux/feeds.json"])

    def test_subscription_play_default_plan_check_guard_and_synchronous_results(self):
        play, = yaml.safe_load((ROOT / "src/miniflux-subscriptions.yml").read_text())
        self.assertEqual(play["hosts"], "habiki")
        self.assertIn("default(false)", play["vars"]["subscription_unit"])
        block = play["tasks"][1]
        self.assertEqual(block["when"], "not ansible_check_mode")
        start = block["block"][0]
        self.assertEqual(start["ansible.builtin.command"]["argv"][:2], ["systemctl", "start"])
        self.assertNotIn("--no-block", start["ansible.builtin.command"]["argv"])
        journal, = [t for t in block["block"] if t.get("register") == "subscription_journal"]
        self.assertIn("--invocation=0", journal["ansible.builtin.command"]["argv"])
        self.assertNotIn("when", journal)  # Successful inactive units clear InvocationID.
        self.assertIn("subscription_result.rc == 0", block["block"][-1]["ansible.builtin.assert"]["that"])
        self.assertNotIn("miniflux-subscriptions", (ROOT / "src/playbook.yml").read_text())

    def test_identity_apply_refresh_precedes_ansible_consumer_load(self):
        result, calls = self.run_play(["--limit", "habiki", "--tags", "miniflux"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls[0], ["tofu.sh", "--", "apply", "-auto-approve", "-target=authentik_policy_binding.miniflux_access"])
        self.assertEqual(calls[1][0], "ansible-playbook")
        self.assertIn("habiki", calls[1])
        self.assertIn("miniflux", calls[1])
        wrapper = (ROOT / "scripts/tofu.sh").read_text()
        self.assertIn("refresh_generated_secrets", wrapper.split('if [[ " ${TOFU_ARGS[*]} "')[1])

    def test_other_host_unbounded_target_and_stale_refresh_are_rejected(self):
        for args in (["--tags", "miniflux"], ["--limit", "fyne", "--tags", "miniflux"],
                     ["--limit", "habiki", "--tags", "miniflux", "--skip-generated-refresh"],
                     ["--limit", "habiki", "--tags", "miniflux", "--", "--limit=fyne"],
                     ["--limit", "habiki", "--tags", "miniflux", "--", "--tags=nixos"]):
            with self.subTest(args=args):
                result, calls = self.run_play(args)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, [])

    def test_check_and_listing_modes_do_not_mutate_infrastructure(self):
        for flag in ("--check", "--syntax-check", "--list-tasks", "--list-hosts"):
            result, calls = self.run_play(["--limit", "habiki", "--tags", "miniflux", "--", flag])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual([call[0] for call in calls], ["ansible-playbook"])

    def test_consumer_role_order_and_unrelated_maintenance_guards(self):
        plays = yaml.safe_load((ROOT / "src/playbook.yml").read_text())
        selected = [role["role"] for role in plays[1]["roles"] if "miniflux" in role.get("tags", [])]
        self.assertEqual(selected, ["secrets", "nixos"])
        tasks = yaml.safe_load((ROOT / "src/roles/nixos/tasks/main.yml").read_text())
        for task in tasks:
            if task.get("ansible.builtin.include_tasks") in ("channel.yml", "podman.yml", "headscale-enrolment.yml", "garage-provisioning.yml"):
                self.assertIn("nixos_miniflux_only", task["when"])
        defaults = (ROOT / "src/roles/nixos/defaults/main.yml").read_text()
        self.assertIn("ansible_run_tags | length == 1", defaults)

    def test_tofu_local_checks_do_not_load_credentials_or_initialize_backend(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            scripts = base / "scripts"
            scripts.mkdir()
            (base / "terraform").mkdir()
            shutil.copyfile(ROOT / "scripts/tofu.sh", scripts / "tofu.sh")
            stub = scripts / "tofu"
            stub.write_text(f"#!{sys.executable}\nimport json, sys\nprint(json.dumps(sys.argv[1:]))\n")
            stub.chmod(0o700)
            env = dict(os.environ, HOME=str(base / "no-home"), PATH=str(scripts) + os.pathsep + os.environ["PATH"])
            for command in ("fmt", "validate"):
                result = subprocess.run(["bash", str(scripts / "tofu.sh"), "--", command],
                                        cwd=base, env=env, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                expected = [command] if command == "fmt" else ["-chdir=" + str(base / "terraform"), command]
                self.assertEqual(json.loads(result.stdout), expected)

    def test_legacy_dns_only_run_does_not_provision_identity(self):
        result, calls = self.run_play(["--limit", "fyne", "--tags", "local-dns"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([call[0] for call in calls], ["ansible-playbook"])
