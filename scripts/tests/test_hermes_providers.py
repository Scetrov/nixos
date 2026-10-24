"""Synthetic managed-provider reconciliation: no production state or credentials."""

from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from jinja2 import Environment, StrictUndefined
import yaml


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "src/roles/nixos/files/etc/nixos/modules"
spec = importlib.util.spec_from_file_location("hermes_config", MODULE / "hermes-config.py")
reconciler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reconciler)


def settings():
    return {
        "defaultModel": "existing/model", "modelEnvVar": "HERMES_DEFAULT_MODEL",
        "provider": "openrouter", "baseUrl": "https://openrouter.ai/api/v1",
        "localQwen": {"enable": False, "baseUrl": None, "model": None,
                      "contextLength": None, "requireApiKey": False},
    }


class HermesProviderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.config = self.home / "config.yaml"
        self.webui = self.home / "webui.env"
        self.options = settings()
        self.env = {}

    def run_reconcile(self):
        reconciler.reconcile(self.home, self.webui, self.options, self.env, os.getuid(), os.getgid())
        return yaml.safe_load(self.config.read_text())

    def enable_local(self):
        self.options["localQwen"].update(
            enable=True, baseUrl="http://qwen.invalid:8000/v1", model="fixture-qwen", contextLength=65536,
        )

    def test_backwards_compatible_default_and_override(self):
        result = self.run_reconcile()
        self.assertEqual(result["model"]["provider"], "openrouter")
        self.assertNotIn("providers", result)
        self.assertEqual(self.webui.read_text(), "HERMES_WEBUI_DEFAULT_MODEL=existing/model\n")
        self.env["HERMES_DEFAULT_MODEL"] = "override/model"
        self.assertEqual(self.run_reconcile()["model"]["default"], "override/model")

    def test_enable_disable_idempotence_and_state_preservation(self):
        original = {"model": {"temperature": 0.4}, "tools": {"terminal": "local"},
                    "providers": {"unmanaged": {"api": "http://other.invalid/v1"}},
                    "custom_providers": [{"name": "legacy", "base_url": "http://legacy.invalid/v1"}]}
        self.config.write_text(yaml.safe_dump(original))
        for name in ("auth.json", "sessions.db", "cron-state.json"):
            (self.home / name).write_bytes(b"synthetic-native-state")
        self.enable_local()
        first = self.run_reconcile()
        self.assertEqual(first, self.run_reconcile())
        self.assertEqual(first["model"]["temperature"], 0.4)
        self.assertEqual(first["tools"], original["tools"])
        self.assertEqual(first["custom_providers"], original["custom_providers"])
        self.assertNotIn("key_env", first["providers"]["local-qwen"])
        self.assertEqual(first["providers"]["local-qwen"]["models"]["fixture-qwen"]["context_length"], 65536)
        self.options["localQwen"]["enable"] = False
        self.assertEqual(self.run_reconcile()["providers"], original["providers"])
        for name in ("auth.json", "sessions.db", "cron-state.json"):
            self.assertEqual((self.home / name).read_bytes(), b"synthetic-native-state")

    def test_required_key_reference_not_value_and_custom_default(self):
        self.enable_local()
        self.options["localQwen"]["requireApiKey"] = True
        self.options["provider"] = "custom:local-qwen"
        self.options["defaultModel"] = "fixture-qwen"
        self.options["baseUrl"] = "http://qwen.invalid:8000/v1"
        with self.assertRaises(ValueError):
            self.run_reconcile()
        self.env["HERMES_LOCAL_QWEN_API_KEY"] = "synthetic-sensitive-value"
        result = self.run_reconcile()
        self.assertEqual(result["providers"]["local-qwen"]["key_env"], "HERMES_LOCAL_QWEN_API_KEY")
        for path in self.home.iterdir():
            self.assertNotIn("synthetic-sensitive-value", path.read_text())
        self.assertEqual(self.webui.read_text(), "HERMES_WEBUI_DEFAULT_MODEL=@custom:local-qwen:fixture-qwen\n")

    def test_invalid_inputs_preserve_all_outputs(self):
        self.run_reconcile()
        before = {path: path.read_bytes() for path in self.home.iterdir()}
        invalid = [
            {"baseUrl": "http://user:synthetic-secret@qwen.invalid/v1"},
            {"baseUrl": "http://qwen.invalid/v1?token=synthetic-secret"},
            {"baseUrl": "file:///tmp/endpoint"}, {"baseUrl": None},
            {"model": None}, {"model": "model\nnew: injected"},
            {"contextLength": 0}, {"contextLength": True},
        ]
        for changes in invalid:
            with self.subTest(changes=changes):
                self.options = settings()
                self.enable_local()
                self.options["localQwen"].update(changes)
                with self.assertRaises((ValueError, TypeError)):
                    self.run_reconcile()
                self.assertEqual(before, {path: path.read_bytes() for path in self.home.iterdir()})

    def test_malformed_yaml_and_wrong_shapes_preserve_original(self):
        for content in ("model: [", "[]", "null", "model: []", "providers: []"):
            with self.subTest(content=content):
                self.config.write_text(content)
                with self.assertRaises((ValueError, yaml.YAMLError)):
                    self.run_reconcile()
                self.assertEqual(self.config.read_text(), content)

    def test_conflicts_and_edited_owned_definition_are_not_deleted(self):
        self.config.write_text("providers:\n  local-qwen:\n    api: http://unmanaged.invalid/v1\n")
        with self.assertRaises(ValueError):
            self.run_reconcile()
        self.config.unlink()
        self.enable_local()
        result = self.run_reconcile()
        result["providers"]["local-qwen"]["api"] = "http://edited.invalid/v1"
        self.config.write_text(yaml.safe_dump(result))
        self.options["localQwen"]["enable"] = False
        with self.assertRaises(ValueError):
            self.run_reconcile()
        self.assertEqual(yaml.safe_load(self.config.read_text()), result)

    def test_permissions_ownership_and_atomic_replace_failure(self):
        self.run_reconcile()
        for path in self.home.iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.stat().st_uid, os.getuid())
            self.assertEqual(path.stat().st_gid, os.getgid())
        before = self.config.read_bytes()
        self.env["HERMES_DEFAULT_MODEL"] = "other/model"
        with patch.object(reconciler.os, "replace", side_effect=OSError("synthetic failure")):
            with self.assertRaises(OSError):
                self.run_reconcile()
        self.assertEqual(self.config.read_bytes(), before)
        self.assertFalse(list(self.home.glob(".hermes-config-*")))

    def test_symlink_refused_and_cli_errors_are_redacted(self):
        target = self.home / "auth.json"
        target.write_text("synthetic-secret: [")
        self.config.symlink_to(target)
        with self.assertRaises(ValueError):
            self.run_reconcile()
        self.config.unlink()
        self.config.write_text("synthetic-secret: [")
        options = self.home / "settings.json"
        options.write_text(json.dumps(self.options))
        result = subprocess.run([
            sys.executable, str(MODULE / "hermes-config.py"), "--settings", str(options),
            "--home", str(self.home), "--webui-env", str(self.webui),
            "--uid", str(os.getuid()), "--gid", str(os.getgid()),
        ], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("synthetic-secret", result.stdout + result.stderr)
        self.assertIn("redacted", result.stderr)

    def test_environment_parsing_does_not_execute_shell(self):
        path = self.home / "environment"
        path.write_text('# comment\nHERMES_DEFAULT_MODEL="valid/model"\nKEY=$(false)\n')
        self.assertEqual(reconciler.environment(path), {"HERMES_DEFAULT_MODEL": "valid/model", "KEY": "$(false)"})

    def test_both_setup_modes_use_one_reconciler_and_focused_copy(self):
        source = (MODULE / "hermes.nix").read_text()
        self.assertEqual(source.count("${./hermes-config.py}"), 1)
        self.assertIn("${reconcileConfig}", source)
        self.assertNotIn('> "$home_mount/config.yaml"', source)
        self.assertIn("modules/hermes-config.py", (ROOT / "src/hermes-runtime.yml").read_text())


class HermesProviderSecretTests(unittest.TestCase):
    def test_optional_credentials_and_no_subscription_placeholders(self):
        template = Environment(undefined=StrictUndefined, trim_blocks=True).from_string(
            (ROOT / "src/roles/secrets/templates/hermes-webui.env.j2").read_text())
        for value in (None, "", " \n", "fixture-key"):
            arguments = {} if value is None else {"hermes_local_qwen_api_key": value}
            rendered = template.render(**arguments)
            self.assertNotIn("OPENROUTER_API_KEY", rendered)
            self.assertEqual("HERMES_LOCAL_QWEN_API_KEY=" in rendered, value == "fixture-key")
            self.assertNotIn("OPENAI_API_KEY", rendered)
            self.assertNotIn("REFRESH_TOKEN", rendered)
        self.assertIn("OPENROUTER_API_KEY=fixture-router", template.render(openrouter_api_key="fixture-router"))

    def test_vault_addition_preserves_existing_values_without_plaintext_files(self):
        spec = importlib.util.spec_from_file_location("hermes_vault", ROOT / "scripts/provision_hermes_vault.py")
        vault_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vault_module)
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory) / "secrets.yml"
            vault.write_bytes(b"$ANSIBLE_VAULT;old-ciphertext")
            original = vault.read_bytes()
            for field in (None, "", "fixture-existing-key"):
                view = "unrelated: fixture-preserved\n"
                if field is not None:
                    view += "hermes_local_qwen_api_key: " + json.dumps(field) + "\n"

                def fake_vault(command, **kwargs):
                    if command[1] == "view":
                        return subprocess.CompletedProcess(command, 0, stdout=view)
                    self.assertNotIn("fixture-preserved", " ".join(command))
                    updated = yaml.safe_load(kwargs["input"])
                    self.assertEqual(updated, {"unrelated": "fixture-preserved", "hermes_local_qwen_api_key": ""})
                    Path(command[command.index("--output") + 1]).write_bytes(b"$ANSIBLE_VAULT;new-ciphertext")
                    return subprocess.CompletedProcess(command, 0)

                with patch.object(vault_module.subprocess, "run", side_effect=fake_vault) as run:
                    changed = vault_module.provision(vault, Path(directory) / "password")
                    self.assertEqual(changed, field is None)
                    self.assertEqual(run.call_count, 2 if field is None else 1)
                self.assertEqual(list(Path(directory).iterdir()), [vault])
                vault.write_bytes(original)
            with patch.object(vault_module.subprocess, "run", side_effect=[
                subprocess.CompletedProcess([], 0, stdout="unrelated: fixture-preserved\n"),
                subprocess.CalledProcessError(1, "ansible-vault"),
            ]):
                with self.assertRaises(subprocess.CalledProcessError):
                    vault_module.provision(vault, Path(directory) / "password")
            self.assertEqual(vault.read_bytes(), original)
            self.assertEqual(list(Path(directory).iterdir()), [vault])


class HermesExecutionProbeTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            "execution_probe", ROOT / "scripts/tests/check_hermes_provider_execution.py")
        self.probe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.probe)
        self.events = [
            {"type": "tool_use", "name": "terminal", "input": {"command": self.probe.COMMAND}},
            {"type": "tool_result", "name": "terminal", "is_error": False, "output": self.probe.MARKER},
            {"type": "result", "exit_code": 0, "text": self.probe.MARKER},
        ]

    def check(self, events):
        result = subprocess.CompletedProcess([], 0, stdout="\n".join(json.dumps(e) for e in events),
                                             stderr="synthetic-sensitive-diagnostic")
        output = io.StringIO()
        with patch.object(self.probe.subprocess, "run", return_value=result) as run, redirect_stdout(output):
            passed = self.probe.check("custom:local-qwen", "fixture-model")
        self.assertNotIn("synthetic-sensitive-diagnostic", output.getvalue())
        self.assertIn("--provider", run.call_args.args[0])
        self.assertIn("custom:local-qwen", run.call_args.args[0])
        self.assertEqual(run.call_args.kwargs["timeout"], 120)
        return passed

    def test_success_requires_actual_tool_and_final_result(self):
        self.assertTrue(self.check(self.events))
        self.assertFalse(self.check(self.events[2:]))

    def test_wrong_command_or_error_is_not_acceptance(self):
        self.events[0]["input"]["command"] = "different command"
        self.assertFalse(self.check(self.events))
        self.events[0]["input"]["command"] = self.probe.COMMAND
        self.events[1]["is_error"] = True
        self.assertFalse(self.check(self.events))

    def test_malformed_event_fields_fail_closed(self):
        self.events[0]["input"] = None
        self.events[2]["text"] = None
        self.assertFalse(self.check(self.events))

    def test_timeout_is_bounded_and_does_not_print_partial_output(self):
        output = io.StringIO()
        with patch.object(self.probe.subprocess, "run", side_effect=subprocess.TimeoutExpired(
                "hermes", 120, output="synthetic-sensitive-partial")), redirect_stdout(output):
            self.assertFalse(self.probe.check("openai-codex", "fixture-model"))
        self.assertNotIn("synthetic-sensitive-partial", output.getvalue())


if __name__ == "__main__":
    unittest.main()
