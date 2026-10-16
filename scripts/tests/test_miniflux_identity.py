"""Offline identity/credential regression checks; fixtures contain no real secrets.

These inspect the declared authorization boundary, not live Authentik policy
execution. Operator-assisted deny-path checks remain a deployment gate.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.tests.test_render_generated_secrets import RenderError, render, valid_outputs

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
# The verifier is also executable directly from scripts/ on the consumer.
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("verify_miniflux_oidc", SCRIPTS / "verify_miniflux_oidc.py")
assert SPEC and SPEC.loader
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class IdentityTests(unittest.TestCase):
    def test_operator_only_binding_and_strict_confidential_provider(self):
        text = (ROOT / "terraform/miniflux.tf").read_text()
        self.assertIn('client_type        = "confidential"', text)
        self.assertIn('matching_mode     = "strict"', text)
        self.assertIn('https://feed.net.scetrov.live/oauth2/oidc/callback', text)
        self.assertIn('users = [data.authentik_user.scetrov.id]', text)
        self.assertIn('group   = authentik_group.miniflux_operator.id', text)
        self.assertIn('target  = authentik_application.miniflux.uuid', text)
        self.assertNotIn('authentik_group.all_applications', text)
        self.assertNotIn('authentik_group.general_user', text)
        self.assertNotIn('resource "authentik_user"', text)
        self.assertEqual(text.count('sensitive = true'), 2)

    def test_consumer_secrets_are_conditional_and_protected(self):
        tasks = (ROOT / "src/roles/secrets/tasks/main.yml").read_text()
        self.assertIn("when: miniflux_enabled | default(false)", tasks)
        self.assertIn("Validate generated Miniflux OIDC values", tasks)
        consumer = (ROOT / "src/roles/secrets/tasks/miniflux.yml").read_text()
        self.assertEqual(consumer.count("no_log: true"), 2)
        self.assertIn("miniflux_db_password is defined", consumer)
        self.assertNotIn("lookup('password'", consumer)
        runtime = (ROOT / "src/roles/nixos/files/etc/nixos/modules/miniflux.nix").read_text()
        self.assertIn('mode = "0400"', runtime)
        self.assertIn('serviceConfig.LoadCredential', runtime)
        self.assertNotIn('builtins.readFile', runtime)

    def test_generated_values_reject_invalid_input_without_disclosure(self):
        for key in ("miniflux_oidc_client_id", "miniflux_oidc_client_secret"):
            for invalid in (None, "", "  ", "null", "PLACEHOLDER", "secret_placeholder", "changeme", {}, []):
                with self.subTest(key=key, invalid=type(invalid).__name__):
                    outputs = valid_outputs(**{key: {"value": invalid}})
                    with self.assertRaises(RenderError):
                        render(outputs)
            outputs = valid_outputs()
            del outputs[key]
            with self.assertRaises(RenderError):
                render(outputs)

    def test_rotation_and_repeatability(self):
        before = render(valid_outputs())
        self.assertEqual(before, render(valid_outputs()))
        after = render(valid_outputs(miniflux_oidc_client_secret={"value": "rotated-fixture"}))
        self.assertEqual(after, before.replace("miniflux-secret-fixture", "rotated-fixture"))

    def test_client_id_is_yaml_escaped(self):
        value = 'fixture"\nother: value'
        result = render(valid_outputs(miniflux_oidc_client_id={"value": value}))
        self.assertIn('miniflux_oidc_client_id: ' + json.dumps(value), result)

    def test_consistency_reports_only_redacted_status(self):
        with tempfile.TemporaryDirectory() as directory:
            client_id, client_secret = (Path(directory) / name for name in ("id", "secret"))
            client_id.write_text("miniflux-id-fixture")
            client_secret.write_text("miniflux-secret-fixture")
            for content, expected_rc in (("miniflux-secret-fixture", 0), ("wrong-secret-fixture", 1)):
                client_secret.write_text(content)
                stdout = io.StringIO()
                argv = ["verify", "--client-id-file", str(client_id), "--client-secret-file", str(client_secret)]
                with patch.object(sys, "argv", argv), patch.object(sys, "stdin", io.StringIO(json.dumps(valid_outputs()))), contextlib.redirect_stdout(stdout):
                    self.assertEqual(verifier.main(), expected_rc)
                self.assertEqual(stdout.getvalue(), "Miniflux OIDC: " + ("OK match=true\n" if expected_rc == 0 else "FAIL match=false\n"))
                self.assertNotIn(content, stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
