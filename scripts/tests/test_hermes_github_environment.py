"""Exercise Hermes secret rendering with non-sensitive fixtures only."""
from pathlib import Path
import unittest

from jinja2 import Environment, StrictUndefined
import yaml


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "src/roles/secrets/templates/hermes-webui.env.j2"


class HermesEnvironmentTests(unittest.TestCase):
    def render(self, **github):
        template = Environment(
            undefined=StrictUndefined, trim_blocks=True, keep_trailing_newline=True,
        ).from_string(TEMPLATE.read_text())
        return template.render(
            openrouter_api_key="fixture-provider",
            **github,
        )

    def entries(self, rendered):
        lines = rendered.splitlines()
        self.assertTrue(all("=" in line for line in lines))
        entries = dict(line.split("=", 1) for line in lines)
        self.assertEqual(len(lines), len(entries))
        return entries

    def test_existing_configuration_without_github_is_preserved(self):
        self.assertEqual(self.entries(self.render()), {
            "OPENROUTER_API_KEY": "fixture-provider",
            "HERMES_DEFAULT_MODEL": "qwen/qwen3.6-flash",
        })

    def test_legacy_password_is_not_rendered(self):
        entries = self.entries(self.render(hermes_webui_password="fixture-password"))
        self.assertNotIn("HERMES_WEBUI_PASSWORD", entries)

    def test_all_vault_fields_reach_the_expected_environment_variables(self):
        entries = self.entries(self.render(
            hermes_github_token="fixture-token",
            hermes_github_app_id=1234,
            hermes_github_client_id="fixture-client",
            hermes_github_client_secret="fixture-secret",
            hermes_github_private_key="fixture-key",
            hermes_github_installation_id=5678,
            hermes_default_model="fixture/model",
        ))
        self.assertEqual(entries["GH_TOKEN"], "fixture-token")
        self.assertEqual(entries["GITHUB_APP_ID"], "1234")
        self.assertEqual(entries["GITHUB_APP_CLIENT_ID"], "fixture-client")
        self.assertEqual(entries["GITHUB_APP_CLIENT_SECRET"], "fixture-secret")
        self.assertEqual(entries["GITHUB_APP_PRIVATE_KEY"], "fixture-key")
        self.assertEqual(entries["GITHUB_APP_INSTALLATION_ID"], "5678")
        self.assertEqual(entries["HERMES_DEFAULT_MODEL"], "fixture/model")

    def test_pem_is_one_physical_line_and_round_trips_for_plugin(self):
        pem = "-----BEGIN PRIVATE KEY-----\nfixture+/=\n-----END PRIVATE KEY-----"
        for value in [pem + "\n", pem.replace("\n", "\r\n"), pem.replace("\n", "\\n")]:
            with self.subTest(value=value):
                entries = self.entries(self.render(hermes_github_private_key=value))
                self.assertEqual(entries["GITHUB_APP_PRIVATE_KEY"].replace("\\n", "\n"), pem)
                self.assertNotIn("\r", entries["GITHUB_APP_PRIVATE_KEY"])

    def test_missing_installation_id_is_not_invented(self):
        entries = self.entries(self.render(hermes_github_app_id=1234))
        self.assertNotIn("GITHUB_APP_INSTALLATION_ID", entries)

    def test_empty_optional_fields_are_omitted(self):
        entries = self.entries(self.render(hermes_github_private_key=" \n"))
        self.assertFalse(any(key.startswith("GITHUB_") for key in entries))
        self.assertNotIn("GH_TOKEN", entries)

    def test_secret_generation_uses_template_under_no_log(self):
        tasks = yaml.safe_load((ROOT / "src/roles/secrets/tasks/main.yml").read_text())
        task = next(task for task in tasks if task.get("name") == "Define filenames dynamically")
        self.assertTrue(task["no_log"])
        secret = next(item for item in task["set_fact"]["age_secrets"]
                      if item["name"] == "hermes_webui_env")
        self.assertEqual(secret["content"], "{{ lookup('ansible.builtin.template', 'hermes-webui.env.j2') }}")

    def test_gateway_and_webui_agent_runtimes_get_static_github_cli(self):
        module = (ROOT / "src/roles/nixos/files/etc/nixos/modules/hermes.nix").read_text()
        mount = '"${cfg.githubCliPackage}/bin/gh:/usr/local/bin/gh:ro"'
        for name in ["hermes-agent", "hermes-webui"]:
            block = module.split(f"      {name} = {{", 1)[1].split("// podmanRootlessConfig", 1)[0]
            self.assertIn(mount, block)
        self.assertEqual(module.count(mount), 2)
        self.assertIn("pkgs.pkgsStatic.github-cli", module)
        self.assertIn("readelf -l", module)
        self.assertNotIn("hermes_github_token", module)

    def test_habiki_uses_private_backend_and_trusted_proxy_without_password(self):
        host = (ROOT / "src/roles/nixos/files/device-configuration/habiki.nix").read_text()
        block = host.split("  services.hermes-webui = {", 1)[1].split("\n  age.secrets.", 1)[0]
        self.assertNotIn("HERMES_WEBUI_PASSWORD", block)
        self.assertIn('caddyListenAddress = "127.0.0.1";', block)
        self.assertIn('HERMES_WEBUI_TRUSTED_PROXY_AUTH_HEADER = "X-Authentik-Username";', block)

    def test_webui_is_not_published_when_caddy_is_enabled(self):
        module = (ROOT / "src/roles/nixos/files/etc/nixos/modules/hermes.nix").read_text()
        block = module.split("      hermes-webui = {", 1)[1].split("// podmanRootlessConfig", 1)[0]
        self.assertIn(
            'ports = lib.optional (!cfg.enableCaddy) "${cfg.caddyListenAddress}:${toString cfg.webuiPort}:8787";',
            block,
        )

    def test_nixos_passes_runtime_environment_to_all_app_containers(self):
        module = (ROOT / "src/roles/nixos/files/etc/nixos/modules/hermes.nix").read_text()
        for name in ["hermes-agent", "hermes-webui", "hermes-dashboard"]:
            block = module.split(f"      {name} = {{", 1)[1].split("// podmanRootlessConfig", 1)[0]
            self.assertIn("environmentFiles = optionalEnvFiles", block)
        self.assertIn('-m0600 ${lib.escapeShellArg cfg.environmentFile} "$home_mount/.env"', module)
