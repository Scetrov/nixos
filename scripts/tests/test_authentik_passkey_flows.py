"""Offline guardrails for unselected passkey-first candidate configuration.

These checks do not assert that a real WebAuthn ceremony or browser UX passed.
"""

from pathlib import Path
import re
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = ROOT / "terraform/authentik-flows.tf"


def block(source, kind, resource_type, name):
    match = re.search(
        rf'{kind} "{resource_type}" "{name}"\s*\{{(.*?)^\}}',
        source,
        re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"Missing {kind} {resource_type}.{name}")
    return match.group(1)


class PasskeyCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = CANDIDATES.read_text()

    def resource(self, resource_type, name):
        return block(self.source, "resource", resource_type, name)

    def test_candidates_do_not_adopt_or_mutate_existing_objects(self):
        allowed = {
            "authentik_flow",
            "authentik_stage_identification",
            "authentik_stage_authenticator_validate",
            "authentik_stage_redirect",
            "authentik_flow_stage_binding",
            "authentik_policy_expression",
            "authentik_policy_binding",
        }
        types = re.findall(r'^resource "([^"]+)"', self.source, re.MULTILINE)
        self.assertTrue(types)
        self.assertLessEqual(set(types), allowed)
        for body in re.findall(
            r'^resource "authentik_flow" "[^"]+"\s*\{(.*?)^\}',
            self.source,
            re.MULTILINE | re.DOTALL,
        ):
            self.assertRegex(body, r'slug\s*=\s*"[^"\n]+-candidate"')
        self.assertNotRegex(self.source, r"(?m)^\s*(import|removed)\s*\{")
        active = (ROOT / "terraform/authentik.tf").read_text()
        self.assertRegex(
            block(active, "resource", "authentik_brand", "default"),
            r"flow_authentication\s*=\s*var\.authentik_passkey_first_enabled\s*\?\s*"
            r"authentik_flow\.passkey_candidate\.uuid\s*:\s*"
            r"data\.authentik_flow\.default_authentication\.id",
        )

    def test_passkey_configuration_does_not_customize_native_presentation(self):
        active = (ROOT / "terraform/authentik.tf").read_text()
        self.assertNotIn("authentik-passkey.css", active)
        self.assertFalse((ROOT / "terraform/authentik-passkey.css").exists())
        brand = block(active, "resource", "authentik_brand", "default")
        self.assertNotIn("passkey-explicit-candidate", brand)
        self.assertRegex(brand, r"branding_custom_css\s*=\s*trimspace\(")

    def test_accepted_selection_and_rollback_keep_existing_flow(self):
        variables = (ROOT / "terraform/variables.tf").read_text()
        switch = re.search(
            r'variable "authentik_passkey_first_enabled"\s*\{(.*?)^\}',
            variables, re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(switch)
        self.assertRegex(switch.group(1), r"type\s*=\s*bool")
        self.assertRegex(switch.group(1), r"default\s*=\s*true")
        active = (ROOT / "terraform/authentik.tf").read_text()
        fallback = block(active, "data", "authentik_flow", "default_authentication")
        self.assertIn('slug = "default-authentication-flow"', fallback)

    def test_fallback_reuses_password_and_mfa_without_weakening_them(self):
        for suffix in ("password", "mfa"):
            with self.subTest(stage=suffix):
                data = block(
                    self.source, "data", "authentik_stage", f"fallback_{suffix}"
                )
                expected = (
                    "default-authentication-password"
                    if suffix == "password"
                    else "default-authentication-mfa-validation"
                )
                self.assertIn(f'"{expected}"', data)
                binding = self.resource(
                    "authentik_flow_stage_binding", f"passkey_fallback_{suffix}"
                )
                self.assertIn(f"data.authentik_stage.fallback_{suffix}.id", binding)
                self.assertRegex(binding, r"evaluate_on_plan\s*=\s*false")
                self.assertRegex(binding, r"re_evaluate_policies\s*=\s*true")
                policy = self.resource(
                    "authentik_policy_binding", f"passkey_fallback_{suffix}"
                )
                self.assertRegex(policy, r"failure_result\s*=\s*true")
                self.assertIn("passkey_candidate_needs_fallback.id", policy)

    def test_only_current_native_success_skips_fallback(self):
        policy = self.resource(
            "authentik_policy_expression", "passkey_candidate_needs_fallback"
        )
        expression = re.search(r"<<-PYTHON\n(.*?)\n\s*PYTHON", policy, re.DOTALL)
        self.assertIsNotNone(expression)
        import textwrap

        body = textwrap.dedent(expression.group(1))
        namespace = {}
        exec("def evaluate(request):\n" + textwrap.indent(body, "    "), namespace)
        evaluate = namespace["evaluate"]
        for method, should_execute in [
            (None, True),
            ("auth_password", True),
            ("auth_mfa", True),
            ("auth_webauthn_pwl", False),
        ]:
            with self.subTest(method=method):
                request = SimpleNamespace(
                    context={"flow_plan": SimpleNamespace(context={"auth_method": method})},
                    GET={"auth_method": "auth_webauthn_pwl", "passkey_success": "true"},
                    POST={"auth_method": "auth_webauthn_pwl"},
                )
                self.assertEqual(evaluate(request), should_execute)
        self.assertTrue(evaluate(SimpleNamespace(context={})))
        self.assertTrue(evaluate(SimpleNamespace(
            context={"auth_method": "auth_webauthn_pwl"}
        )))
        self.assertRegex(policy, r"execution_logging\s*=\s*false")

    def test_native_passkey_first_and_same_flow_fallback(self):
        flow = self.resource("authentik_flow", "passkey_candidate")
        self.assertRegex(flow, r'title\s*=\s*"Sign in"')
        identification = self.resource("authentik_stage_identification", "passkey_candidate")
        self.assertIn('"username"', identification)
        self.assertNotIn("webauthn_stage", identification)
        self.assertNotIn("passwordless_flow", identification)
        validation = self.resource("authentik_stage_authenticator_validate", "passkey_candidate")
        self.assertRegex(validation, r'device_classes\s*=\s*\["webauthn"\]')
        self.assertRegex(validation, r'webauthn_user_verification\s*=\s*"required"')
        self.assertRegex(validation, r'not_configured_action\s*=\s*"deny"')
        self.assertRegex(validation, r'last_auth_threshold\s*=\s*"seconds=0"')
        first = self.resource("authentik_flow_stage_binding", "passkey_initial_validation")
        self.assertRegex(first, r"order\s*=\s*10")
        self.assertIn("authentik_flow.passkey_candidate.uuid", first)
        self.assertIn("authentik_stage_authenticator_validate.passkey_candidate.id", first)
        fallback = self.resource("authentik_policy_binding", "passkey_identification")
        self.assertIn("passkey_candidate_needs_fallback.id", fallback)
        self.assertRegex(fallback, r"failure_result\s*=\s*true")

    def test_old_explicit_url_redirects_natively_with_context(self):
        redirect = self.resource("authentik_stage_redirect", "passkey_candidate")
        self.assertRegex(redirect, r'mode\s*=\s*"flow"')
        self.assertRegex(redirect, r"keep_context\s*=\s*true")
        self.assertIn("authentik_flow.passkey_candidate.uuid", redirect)
        alias = self.resource("authentik_flow_stage_binding", "passkey_explicit_validation")
        self.assertIn("authentik_stage_redirect.passkey_candidate.id", alias)
        self.assertNotIn('"passkey_explicit_session"', self.source)

    def test_system_settings_adoption_preserves_baseline_and_uses_native_footer(self):
        settings = (ROOT / "terraform/authentik-settings.tf").read_text()
        self.assertIn('id = "system_settings"', settings)
        self.assertIn("to = authentik_system_settings.default", settings)
        self.assertIn('href = "/if/flow/passkey-first-candidate/?use_password=1"', settings)
        self.assertRegex(settings, r"core_default_app_access\s*=\s*true")
        self.assertRegex(settings, r"default_user_change_email\s*=\s*false")
        self.assertRegex(settings, r"default_user_change_username\s*=\s*false")
        self.assertRegex(settings, r'event_retention\s*=\s*"days=365"')
        self.assertRegex(settings, r"default_token_length\s*=\s*60")

    def test_enrollment_is_fixture_only_without_a_demonstrated_need(self):
        self.assertNotIn("passkey_enrollment", self.source)
        self.assertNotIn('"authentik_stage_authenticator_webauthn"', self.source)
        fixture = (ROOT / "scripts/tests/run_authentik_passkey_browser.py").read_text()
        flow = block(fixture, "resource", "authentik_flow", "passkey_enrollment_candidate")
        self.assertRegex(flow, r'authentication\s*=\s*"require_authenticated"')
        setup = block(
            fixture, "resource", "authentik_stage_authenticator_webauthn",
            "passkey_enrollment_candidate",
        )
        self.assertRegex(setup, r'resident_key_requirement\s*=\s*"required"')
        self.assertRegex(setup, r'user_verification\s*=\s*"required"')

    def test_helper_retains_explicit_existing_flow(self):
        defaults = (ROOT / "src/roles/authentik-config/defaults/main.yml").read_text()
        self.assertIn(
            'authentik_config_admin_recovery_flow_slug: "default-authentication-flow"',
            defaults,
        )
        tasks = (ROOT / "src/roles/authentik-config/tasks/main.yml").read_text()
        calls = re.findall(
            r'files/authentik_login\.py"(.*?)(?=\n\s*register:)',
            tasks,
            re.DOTALL,
        )
        self.assertEqual(len(calls), 4)
        for call in calls:
            self.assertIn("authentik_config_admin_recovery_flow_slug", call)


class PasskeyReturnContextTests(unittest.TestCase):
    """Execute the production return policy; not a browser acceptance claim."""

    @classmethod
    def setUpClass(cls):
        import textwrap

        cls.source = CANDIDATES.read_text()
        policy = block(cls.source, "resource", "authentik_policy_expression", "passkey_candidate_entry")
        expression = re.search(r"<<-PYTHON\n(.*?)\n\s*PYTHON", policy, re.DOTALL)
        namespace = {}
        exec("def evaluate(request):\n" + textwrap.indent(textwrap.dedent(expression.group(1)), "    "), namespace)
        cls.evaluate = staticmethod(namespace["evaluate"])

    def request(self, params, context=None):
        return SimpleNamespace(
            context={"flow_plan": SimpleNamespace(context={} if context is None else context)},
            http_request=SimpleNamespace(session={"authentik/flows/get": params}),
        )

    def test_initial_target_survives_fallback_and_cannot_be_replaced(self):
        target = "/application/o/authorize/?client_id=fixture&state=synthetic"
        request = self.request({"next": target})
        self.assertTrue(self.evaluate(request))
        self.assertEqual(request.context["flow_plan"].context["redirect"], target)
        request.http_request.session["authentik/flows/get"] = {
            "use_password": "1", "next": "/untrusted-replacement/",
            "auth_method": "auth_webauthn_pwl", "passkey_success": "true",
        }
        self.assertFalse(self.evaluate(request))
        self.assertEqual(request.context["flow_plan"].context["redirect"], target)
        self.assertNotIn("auth_method", request.context["flow_plan"].context)

    def test_unsafe_or_oversized_targets_use_a_local_default(self):
        for target in [
            None, 0, [], "", "https://example.invalid/", "//example.invalid/",
            "/\\example.invalid/", "javascript:alert(1)", "relative/path",
            "/path\n", "/path\r", "/path\t", "/path\x00", "/path\x7f", "/" + "a" * 8192,
        ]:
            with self.subTest(target_type=type(target).__name__):
                request = self.request({"next": target})
                self.assertTrue(self.evaluate(request))
                self.assertEqual(request.context["flow_plan"].context["redirect"], "/if/user/")

    def test_native_relative_oauth_query_is_preserved_verbatim(self):
        target = "/application/o/authorize/?client_id=fixture&state=a%2Bb&redirect_uri=https%3A%2F%2Fexample.invalid%2Fcallback"
        request = self.request({"next": target, "use_password": "1"})
        self.assertFalse(self.evaluate(request))
        self.assertEqual(request.context["flow_plan"].context["redirect"], target)

    def test_separate_plans_do_not_share_return_state(self):
        first = self.request({"next": "/first/"})
        second = self.request({"next": "/second/", "use_password": "1"})
        empty = self.request({"use_password": "1"})
        self.evaluate(first)
        self.evaluate(second)
        self.evaluate(empty)
        self.assertEqual(first.context["flow_plan"].context["redirect"], "/first/")
        self.assertEqual(second.context["flow_plan"].context["redirect"], "/second/")
        self.assertEqual(empty.context["flow_plan"].context["redirect"], "/if/user/")

    def test_capture_runs_during_execution_not_cached_planning(self):
        binding = block(self.source, "resource", "authentik_flow_stage_binding", "passkey_initial_validation")
        self.assertRegex(binding, r"evaluate_on_plan\s*=\s*false")
        self.assertRegex(binding, r"re_evaluate_policies\s*=\s*true")
        fallback = block(self.source, "resource", "authentik_policy_binding", "passkey_fallback_password")
        self.assertIn("passkey_candidate_needs_fallback.id", fallback)
        self.assertRegex(fallback, r"failure_result\s*=\s*true")
        self.assertTrue(self.evaluate(SimpleNamespace(context={})))


if __name__ == "__main__":
    unittest.main()
