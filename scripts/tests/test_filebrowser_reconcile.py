"""Offline API-contract and fail-closed enrollment regression coverage."""

import copy
import unittest
import urllib.parse

from scripts.filebrowser_reconcile import ACCOUNT_PERMISSIONS, OPERATOR, QuantumAPI, ReconcileError, desired_scopes, reconcile

ALICE = {"identity_uuid": "11111111-1111-4111-8111-111111111111", "unix_username": "alice"}


class FakeAPI:
    def __init__(self):
        self.operator = {"username": OPERATOR, "loginMethod": "jwt", "permissions": {"admin": True}}
        self.users = {OPERATOR: self.operator}
        self.writes = 0
        self.calls = 0

    def call(self, method, path, body=None):
        self.calls += 1
        name = urllib.parse.parse_qs(urllib.parse.urlsplit(path).query).get("username", [None])[0]
        if method == "GET":
            if name == "self":
                return copy.deepcopy(self.operator)
            return copy.deepcopy(self.users[name] if name else list(self.users.values()))
        self.writes += 1
        data = copy.deepcopy(body["data"])
        if method == "POST":
            self.users[data["username"]] = data
        elif method == "PATCH":
            self.users[name].update(data)
        else:
            raise AssertionError("Unsupported mutation")


class ReconcileTests(unittest.TestCase):
    def test_missing_account_is_oidc_only_and_reapplication_is_read_only(self):
        api = FakeAPI()
        self.assertGreater(reconcile(api, [ALICE], []), 0)
        user = api.users["alice"]
        self.assertEqual(user["loginMethod"], "oidc")
        self.assertEqual(user["scopes"], desired_scopes("alice"))
        self.assertEqual(user["permissions"], ACCOUNT_PERMISSIONS)
        writes = api.writes
        self.assertEqual(reconcile(api, [ALICE], [ALICE]), 0)
        self.assertEqual(api.writes, writes)

    def test_scope_and_global_privilege_drift_is_repaired(self):
        api = FakeAPI()
        reconcile(api, [ALICE], [])
        api.users["alice"]["scopes"].append(desired_scopes("bob")[0])
        api.users["alice"]["permissions"]["admin"] = True
        reconcile(api, [ALICE], [ALICE])
        self.assertEqual(api.users["alice"]["scopes"], desired_scopes("alice"))
        self.assertFalse(api.users["alice"]["permissions"]["admin"])

    def test_case_mismatch_and_unmapped_accounts_have_no_sources_or_admin(self):
        api = FakeAPI()
        api.users["Alice"] = {"username": "Alice", "loginMethod": "oidc", "scopes": desired_scopes("alice"), "permissions": {"admin": True}}
        reconcile(api, [ALICE], [])
        self.assertEqual(api.users["Alice"]["scopes"], [])
        self.assertEqual(api.users["Alice"]["permissions"], ACCOUNT_PERMISSIONS)

    def test_existing_wrong_login_method_is_rejected(self):
        api = FakeAPI()
        api.users["alice"] = {"username": "alice", "loginMethod": "password"}
        with self.assertRaises(ReconcileError):
            reconcile(api, [ALICE], [])
        self.assertEqual(api.writes, 0)

    def test_removal_and_reassignment_are_rejected_before_api_access(self):
        for records in ([], [{**ALICE, "unix_username": "bob"}]):
            api = FakeAPI()
            with self.assertRaises(ReconcileError):
                reconcile(api, records, [ALICE])
            self.assertEqual(api.calls, 0)

    def test_ordinary_enrollment_cannot_overlap_machine_identity(self):
        api = FakeAPI()
        with self.assertRaises(ReconcileError):
            reconcile(api, [{**ALICE, "unix_username": OPERATOR}], [])
        self.assertEqual(api.calls, 0)

    def test_machine_calls_cannot_target_remote_hosts_or_credential_redirects(self):
        for base in ("https://127.0.0.1", "http://example.com", "http://user@127.0.0.1", "http://127.0.0.1/path", "http://127.0.0.1#fragment"):
            with self.assertRaises(ReconcileError):
                QuantumAPI(base, "synthetic-assertion")


if __name__ == "__main__":
    unittest.main()
