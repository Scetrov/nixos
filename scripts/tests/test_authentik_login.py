"""Offline flow-executor and repair-caller regressions; no live credentials."""

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch
import urllib.error


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "src/roles/authentik-config/files/authentik_login.py"
SPEC = importlib.util.spec_from_file_location("authentik_login_under_test", HELPER)
LOGIN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LOGIN)
MARKER = "synthetic-sensitive-challenge-marker"


class LoginChallengeTests(unittest.TestCase):
    def test_identification_with_and_without_embedded_password(self):
        for embedded in (False, True):
            challenge = {"component": "ak-stage-identification"}
            if embedded:
                challenge["password_fields"] = True
            answer = LOGIN.solve_challenge(challenge, "fixture-user", MARKER)
            self.assertEqual(answer["uid_field"], "fixture-user")
            self.assertEqual(answer.get("password"), MARKER if embedded else None)

    def test_password_and_login_challenges(self):
        self.assertEqual(
            LOGIN.solve_challenge({"component": "ak-stage-password"}, "user", MARKER),
            {"component": "ak-stage-password", "password": MARKER},
        )
        self.assertEqual(
            LOGIN.solve_challenge({"component": "ak-stage-user-login"}, "user", MARKER),
            {"component": "ak-stage-user-login", "remember_me": True},
        )
        self.assertIsNone(LOGIN.solve_challenge({"component": "xak-flow-redirect"}, "user", MARKER))

    def test_unexpected_mfa_and_denial_fail_without_echoing_challenge(self):
        for component in ("ak-stage-authenticator-validate", "ak-stage-access-denied", MARKER):
            with self.subTest(component=component):
                errors = io.StringIO()
                with redirect_stderr(errors), self.assertRaises(SystemExit) as raised:
                    LOGIN.solve_challenge(
                        {"component": component, "response_errors": {"secret": MARKER}},
                        "fixture-user", MARKER,
                    )
                self.assertEqual(raised.exception.code, 1)
                self.assertNotIn(MARKER, errors.getvalue())
                self.assertNotIn("response_errors", json.loads(errors.getvalue()))


class LoginExecutorTests(unittest.TestCase):
    def invoke(self, responses, flow="default-authentication-flow"):
        output, errors = io.StringIO(), io.StringIO()
        args = [str(HELPER), "https://identity.example.invalid/api/v3", "fixture-user", MARKER, flow]
        with (
            patch.object(sys, "argv", args),
            patch.object(LOGIN.urllib.request, "build_opener"),
            patch.object(LOGIN, "request_json", side_effect=responses) as request,
            patch.object(LOGIN, "find_cookie", return_value="synthetic-csrf"),
            patch.object(LOGIN, "build_cookie_header", return_value="synthetic-cookie"),
            redirect_stdout(output), redirect_stderr(errors),
        ):
            try:
                LOGIN.main()
                status = 0
            except SystemExit as exc:
                status = exc.code
        return status, output.getvalue(), errors.getvalue(), request.call_args_list

    def test_explicit_compatible_flow_and_challenge_sequence(self):
        status, output, errors, calls = self.invoke([
            {"component": "ak-stage-identification"},
            {"component": "ak-stage-password"},
            {"component": "ak-stage-user-login"},
            {"component": "xak-flow-redirect"},
            {"user": {"pk": 123}},
        ])
        self.assertEqual(status, 0)
        self.assertEqual(errors, "")
        self.assertEqual(json.loads(output)["flow_slug"], "default-authentication-flow")
        self.assertNotIn(MARKER, output)
        self.assertIn("/flows/executor/default-authentication-flow/?query=", calls[0].args[1])
        self.assertEqual(calls[1].kwargs["body"]["uid_field"], "fixture-user")
        self.assertEqual(calls[2].kwargs["body"]["password"], MARKER)
        self.assertEqual(calls[-1].args[1], "https://identity.example.invalid/api/v3/core/users/me/")

    def test_selected_flow_is_escaped_as_one_path_segment(self):
        status, _, _, calls = self.invoke([
            {"component": "xak-flow-redirect"}, {"user": {"pk": 123}},
        ], flow="compatible/flow?next=other")
        self.assertEqual(status, 0)
        self.assertIn("/compatible%2Fflow%3Fnext%3Dother/", calls[0].args[1])

    def test_redirect_without_authenticated_user_does_not_succeed(self):
        status, output, errors, _ = self.invoke([
            {"component": "xak-flow-redirect"}, {"user": {}},
        ])
        self.assertEqual(status, 1)
        self.assertEqual(output, "")
        self.assertNotIn(MARKER, errors)

    def test_unexpected_challenge_stops_before_session_lookup(self):
        status, output, errors, calls = self.invoke([
            {"component": "ak-stage-authenticator-validate", "response_errors": {"raw": MARKER}},
        ])
        self.assertEqual(status, 1)
        self.assertEqual(output, "")
        self.assertEqual(len(calls), 1)
        self.assertNotIn(MARKER, errors)

    def test_loop_is_bounded_and_failure_does_not_echo_component(self):
        status, output, errors, calls = self.invoke([
            {"component": "ak-stage-identification"}
            for _ in range(LOGIN.MAX_CHALLENGE_STEPS + 1)
        ])
        self.assertEqual(status, 1)
        self.assertEqual(len(calls), LOGIN.MAX_CHALLENGE_STEPS + 1)
        self.assertEqual(output, "")
        self.assertNotIn(MARKER, errors)
        self.assertIn("maximum supported steps", errors)

    def test_top_level_http_and_unexpected_errors_are_redacted(self):
        # Exercise the actual command entry point rather than duplicating its catch logic.
        for error in [
            urllib.error.HTTPError("https://example.invalid/" + MARKER, 403, MARKER, {}, io.BytesIO(MARKER.encode())),
            RuntimeError(MARKER),
        ]:
            with self.subTest(error=type(error).__name__):
                output, errors = io.StringIO(), io.StringIO()
                with (
                    patch.object(LOGIN, "main", side_effect=error),
                    redirect_stdout(output), redirect_stderr(errors),
                    self.assertRaises(SystemExit) as raised,
                ):
                    LOGIN.run()
                self.assertEqual(raised.exception.code, 1)
                self.assertEqual(output.getvalue(), "")
                self.assertNotIn(MARKER, errors.getvalue())
                self.assertNotIn("body", json.loads(errors.getvalue()))
                if isinstance(error, urllib.error.HTTPError):
                    self.assertTrue(error.fp.closed, "Close failures without echoing the response")


class RepairOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.tasks = (ROOT / "src/roles/authentik-config/tasks/main.yml").read_text()

    def test_repair_keeps_token_first_and_session_last_resort_order(self):
        names = [
            "Check whether the service-account token already works",
            "Check whether the bootstrap token can repair Authentik state",
            "Log in with the upstream Authentik bootstrap account",
            "Log in with the managed Authentik admin account when bootstrap recovery fails",
            "Reconcile admin identity while preserving application memberships",
            "Repair the service-account token when it is missing",
            "Verify API token through Blueprint service account",
        ]
        positions = [self.tasks.index("- name: " + name) for name in names]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("authentik_config_service_account_token_check.status | default(0) != 200", self.tasks)
        self.assertIn('authentik_config_service_account_blueprint_template', self.tasks)

    def test_login_and_repair_secret_operations_remain_no_log(self):
        tasks = re.split(r"(?m)^\s*- name: ", self.tasks)[1:]
        sensitive = [t for t in tasks if "files/authentik_login.py" in t or "cookie_header:" in t]
        self.assertGreaterEqual(len(sensitive), 4)
        for task in sensitive:
            with self.subTest(task=task.splitlines()[0]):
                self.assertIn("no_log: true", task)

    def test_existing_explicit_flow_is_not_changed_to_passkey_candidate(self):
        defaults = (ROOT / "src/roles/authentik-config/defaults/main.yml").read_text()
        self.assertIn('authentik_config_admin_recovery_flow_slug: "default-authentication-flow"', defaults)
        self.assertNotIn("passkey-first-candidate", self.tasks)
        self.assertNotIn("passkey-explicit-candidate", self.tasks)


if __name__ == "__main__":
    unittest.main()
