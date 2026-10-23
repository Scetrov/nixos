#!/usr/bin/env python3
"""Idempotent, fail-closed Quantum user/scope reconciliation over the public API.

No database writes, password bootstrap, or user-session collection. Operator
administration uses a two-minute Authentik machine assertion on loopback only.
Enrollment removal is deliberately unsupported in this initial family rollout.
"""

import argparse
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

if __package__:
    from .filebrowser_host import validate_enrollments
else:
    from filebrowser_host import validate_enrollments

OPERATOR = "filebrowser-reconciler"
MACHINE_HEADER = "X-Filebrowser-Admin-Assertion"
FILE_PERMISSIONS = {key: True for key in ("view", "download", "modify", "create", "delete")}
ACCOUNT_PERMISSIONS = {key: False for key in ("admin", "api", "share", "realtime")}


class ReconcileError(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise ReconcileError("Unexpected credential-bearing redirect")


def request(url, method, *, headers=None, data=None):
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, headers=headers or {}, data=data, method=method)
    try:
        with opener.open(req, timeout=30) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


class QuantumAPI:
    def __init__(self, base, assertion):
        parsed = urllib.parse.urlsplit(base)
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.username or parsed.path or parsed.query or parsed.fragment:
            raise ReconcileError("Machine administration is loopback only")
        self.base = base
        self.assertion = assertion

    def call(self, method, path, body=None):
        headers = {MACHINE_HEADER: self.assertion}
        if body is not None:
            headers["Content-Type"] = "application/json"
        status, raw = request(self.base + path, method, headers=headers, data=json.dumps(body).encode() if body is not None else None)
        if status not in (200, 201, 204):
            raise ReconcileError("Quantum API request failed")
        return json.loads(raw) if raw.strip() else None


def machine_assertion(client_id, app_password):
    status, body = request("https://identity.net.scetrov.live/application/o/token/", "POST", headers={"Content-Type": "application/x-www-form-urlencoded"}, data=urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": client_id, "username": OPERATOR, "password": app_password, "scope": "profile"}).encode())
    if status != 200:
        raise ReconcileError("Authentik machine authentication failed")
    token = json.loads(body).get("access_token")
    if not isinstance(token, str) or len(token.split(".")) != 3:
        raise ReconcileError("Invalid machine assertion")
    # Signature, algorithm and private-role validation are performed by
    # Quantum. Do not accept an OAuth error page as an assertion or log it.
    return token


def desired_scopes(username):
    return [{"name": username, "scope": "/", "permissions": FILE_PERMISSIONS.copy()}]


def matches(user, scopes):
    current = user.get("scopes") or []
    if len(current) != len(scopes):
        return False
    for actual, desired in zip(current, scopes):
        if actual.get("name") != desired["name"] or actual.get("scope") != desired["scope"]:
            return False
        if any(actual.get("permissions", {}).get(key) != value for key, value in desired["permissions"].items()):
            return False
    return all(user.get("permissions", {}).get(key, False) is False for key in ACCOUNT_PERMISSIONS)


def validate_transition(records, previous):
    validate_enrollments(records)
    old = {entry["identity_uuid"]: entry["unix_username"] for entry in previous}
    new = {entry["identity_uuid"]: entry["unix_username"] for entry in records}
    if set(old) - set(new) or any(old[key] != new[key] for key in set(old) & set(new)):
        raise ReconcileError("Enrollment removal/reassignment requires a separately reviewed revocation procedure")
    if any(entry["unix_username"] in (OPERATOR, "filebrowser", "root") for entry in records):
        raise ReconcileError("Reserved machine identity cannot be an ordinary enrollment")


def reconcile(api, records, previous):
    validate_transition(records, previous)
    operator = api.call("GET", "/api/users?username=self")
    if operator.get("username") != OPERATOR or operator.get("loginMethod") != "jwt" or not operator.get("permissions", {}).get("admin"):
        raise ReconcileError("Machine administrator identity did not match")
    users = api.call("GET", "/api/users")
    if not isinstance(users, list):
        raise ReconcileError("Unexpected user-list API contract")
    by_name = {user["username"]: user for user in users}
    if len(by_name) != len(users):
        raise ReconcileError("Ambiguous Quantum usernames")
    managed = {entry["unix_username"] for entry in records}
    changed = 0
    for name in sorted(managed):
        existing = by_name.get(name)
        if existing is not None and existing.get("loginMethod") != "oidc":
            raise ReconcileError("Managed username has a different authentication method")
        if existing is None:
            # API creation and login share the same deny-all defaults. Assign
            # the scope separately and verify it before publishing readiness.
            api.call("POST", "/api/users", {"data": {"username": name, "loginMethod": "oidc", "permissions": ACCOUNT_PERMISSIONS.copy(), "scopes": []}})
            by_name[name] = api.call("GET", "/api/users?" + urllib.parse.urlencode({"username": name}))
            changed += 1
    for name, user in sorted(by_name.items()):
        if name == OPERATOR:
            continue
        scopes = desired_scopes(name) if name in managed else []
        if not matches(user, scopes):
            api.call("PATCH", "/api/users?" + urllib.parse.urlencode({"username": name}), {"which": ["scopes", "permissions"], "data": {"username": name, "scopes": scopes, "permissions": ACCOUNT_PERMISSIONS.copy()}})
            changed += 1
    for user in api.call("GET", "/api/users"):
        name = user["username"]
        if name != OPERATOR and not matches(user, desired_scopes(name) if name in managed else []):
            raise ReconcileError("Scope or privilege verification failed")
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enrollments", required=True)
    parser.add_argument("--port", type=int, default=8092)
    args = parser.parse_args()
    ready = Path("/run/filebrowser/ready")
    try:
        ready.unlink(missing_ok=True)
        records = json.loads(Path(args.enrollments).read_text())
        previous = json.loads(Path("/var/lib/filebrowser-enrollment/enrollment.json").read_text())["enrollments"]
        validate_transition(records, previous)
        credentials = Path(os.environ["CREDENTIALS_DIRECTORY"])
        assertion = machine_assertion((credentials / "client-id").read_text().strip(), (credentials / "app-password").read_text().strip())
        api = QuantumAPI(f"http://127.0.0.1:{args.port}", assertion)
        for attempt in range(30):
            try:
                status, _ = request(api.base + "/health", "GET")
                if status != 200:
                    raise ReconcileError("Runtime not healthy yet")
                break
            except (OSError, ValueError):
                if attempt == 29:
                    raise
                time.sleep(1)
        changed = reconcile(api, records, previous)
        temporary = ready.with_suffix(".new")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644)
        with os.fdopen(fd, "w") as stream:
            stream.write("ready\n")
        os.chmod(temporary, 0o644)
        os.replace(temporary, ready)
        print(f"Quantum scopes verified; {changed} account updates")
    except Exception:
        print("Quantum reconciliation failed; public route remains unavailable", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
