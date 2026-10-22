#!/usr/bin/env python3
"""Provision Forgejo mirror access through isolated OpenTofu, never import Git.

Temporary admin bootstrap uses supported native CLI via SSH; all permanent
users/organizations/teams are OpenTofu resources. No password API authentication.
Credentials stay in captured pipes/environment, encrypted vault or protected RAM.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
ORG_NAMES = ["gh-Scetrov", "gh-RichardSlater", "gh-storytold"]
BOOTSTRAP_SCOPES = "write:admin,write:organization,read:user"
SERVICE_SCOPES = "write:repository,read:organization"
spec = importlib.util.spec_from_file_location("mirror_api", ROOT / "src/roles/nixos/files/etc/nixos/modules/forgejo-mirrors.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
API = module.API


class ProvisionError(Exception):
    pass


def command(args, missing_state=False, **kwargs):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=300, **kwargs)
    except (OSError, subprocess.SubprocessError):
        raise ProvisionError("Provisioning command could not complete") from None
    if result.returncode:
        if missing_state and result.returncode == 1 and "No state file was found!" in result.stderr:
            return ""
        raise ProvisionError("Provisioning command failed; sensitive output suppressed")
    return result.stdout


def vault_read(vault, password_file):
    return command(["ansible-vault", "view", str(vault), "--vault-password-file", str(password_file)])


def vault_value(plain, key):
    matches = re.findall(r"(?m)^" + re.escape(key) + r":\s*([^\n]+)$", plain)
    if len(matches) > 1:
        raise ProvisionError("Ambiguous managed vault key")
    if not matches:
        return None
    value = matches[0].strip().strip("\"'")
    if not re.fullmatch(r"[0-9a-f]{40,64}", value):
        raise ProvisionError("Invalid managed vault credential")
    return value


def vault_add(vault, password_file, key, value):
    if not re.fullmatch(r"[0-9a-f]{40,64}", value):
        raise ProvisionError("Invalid credential encoding")
    digest = hashlib.sha256(vault.read_bytes()).digest()
    plain = vault_read(vault, password_file)
    existing = vault_value(plain, key)
    if existing:
        if existing != value:
            raise ProvisionError("Refusing credential replacement without rotation approval")
        return
    updated = plain.rstrip() + "\n" + key + ": " + value + "\n"
    fd, path = tempfile.mkstemp(prefix=".forgejo-vault-", dir=vault.parent)
    os.close(fd)
    temporary = Path(path)
    try:
        command(["ansible-vault", "encrypt", "--output", str(temporary), "--vault-password-file", str(password_file)], input=updated)
        if not temporary.read_bytes().startswith(b"$ANSIBLE_VAULT;"):
            raise ProvisionError("Invalid encrypted vault output")
        if hashlib.sha256(vault.read_bytes()).digest() != digest:
            raise ProvisionError("Vault changed concurrently; refusing overwrite")
        temporary.chmod(0o600)
        temporary.replace(vault)
    finally:
        temporary.unlink(missing_ok=True)


class RemoteCLI:
    def __init__(self, host="habiki"):
        self.host = host
        output = command(["ssh", "-o", "BatchMode=yes", host,
                          "systemctl show forgejo --property=ExecStart --value"])
        match = re.search(r"path=(/nix/store/[A-Za-z0-9_.+-]+/bin/forgejo)\s", output)
        if not match:
            raise ProvisionError("Unexpected installed Forgejo binary")
        self.base = ["sudo", "-n", "-u", "forgejo", match[1], "--config",
                     "/var/lib/forgejo/custom/conf/app.ini", "--work-path", "/var/lib/forgejo", "admin", "user"]

    def __call__(self, args):
        return command(["ssh", "-o", "BatchMode=yes", self.host, shlex.join(self.base + args)])


def issue_token(cli, username, name, scopes):
    result = cli(["generate-access-token", "--username", username, "--token-name", name,
                  "--scopes", scopes, "--raw"])
    token = result.strip().splitlines()[-1]
    if not re.fullmatch(r"[0-9a-f]{40}", token):
        raise ProvisionError("Unexpected token issuance result")
    return token


def members(api, team_id):
    rows = api.request("GET", f"/teams/{team_id}/members?limit=100&page=1")
    if not isinstance(rows, list) or len(rows) >= 100:
        raise ProvisionError("Unexpected team membership response")
    return {row["login"].casefold() for row in rows}


def owner_team(api, org):
    rows = api.request("GET", f"/orgs/{org}/teams?limit=100&page=1")
    if not isinstance(rows, list) or len(rows) >= 100:
        raise ProvisionError("Unexpected organization team response")
    found = [row for row in rows if row["name"] == "Owners"]
    if len(found) != 1:
        raise ProvisionError("Ambiguous organization ownership")
    return found[0]["id"]


@contextlib.contextmanager
def bootstrap(cli, base_url, human="scetrov"):
    name = "mirror-bootstrap-" + uuid.uuid4().hex[:16]
    cli(["create", "--username", name, "--email", name + "@source.net.scetrov.live",
         "--admin", "--random-password", "--must-change-password=false"])
    api = None
    try:
        token = issue_token(cli, name, name, BOOTSTRAP_SCOPES)
        api = API(base_url.rstrip("/") + "/api/v1", token)
        yield api, name
    finally:
        # Delete ONLY our unique bootstrap identity, never a namespace/repository.
        # If partial apply left it the sole owner, stop for managed recovery rather
        # than deleting data or removing the last organization owner.
        if api:
            for org in ORG_NAMES:
                if not api.request("GET", "/orgs/" + org):
                    continue
                team = owner_team(api, org)
                owners = members(api, team)
                if name.casefold() in owners:
                    if human.casefold() not in owners:
                        raise ProvisionError("Bootstrap cleanup blocked: permanent human owner missing; managed recovery required")
                    api.request("DELETE", f"/orgs/{org}/members/{name}")
                    if name.casefold() in members(api, team):
                        raise ProvisionError("Bootstrap membership cleanup failed")
        cli(["delete", "--username", name])


def verify(api, outputs, human="scetrov"):
    user = api.request("GET", "/users/forgejo-mirrors")
    if not user or user.get("is_admin") or not user.get("restricted"):
        raise ProvisionError("Dedicated service identity privilege mismatch")
    if set(outputs["namespace_ids"]["value"]) != set(ORG_NAMES):
        raise ProvisionError("Unexpected namespace outputs")
    for org in ORG_NAMES:
        data = api.request("GET", "/orgs/" + org)
        if not data or data["id"] != outputs["namespace_ids"]["value"][org] or data["visibility"] != "private":
            raise ProvisionError("Namespace identity/access mismatch")
        owners = members(api, outputs["owner_team_ids"]["value"][org])
        if human.casefold() not in owners or "forgejo-mirrors" not in owners:
            raise ProvisionError("Approved human/service ownership mismatch")
    organizations = api.request("GET", "/users/forgejo-mirrors/orgs?limit=100&page=1")
    if not isinstance(organizations, list) or {org["name"] for org in organizations} != set(ORG_NAMES):
        raise ProvisionError("Service organization membership exceeds approved scope")


def provision(vault, password_file):
    os.umask(0o077)
    password = vault_value(vault_read(vault, password_file), "forgejo_mirrors_password")
    if not password:
        vault_add(vault, password_file, "forgejo_mirrors_password", secrets.token_hex(32))
    wrapper = [str(ROOT / "scripts/tofu.sh"), "--forgejo-mirrors", "--"]
    # Initialize/check state BEFORE creating any temporary production identity.
    state = command(wrapper + ["state", "list"], missing_state=True)
    cli = RemoteCLI()
    with bootstrap(cli, "https://source.net.scetrov.live") as (api, _):
        if not state.strip():
            if api.request("GET", "/users/forgejo-mirrors") or any(api.request("GET", "/orgs/" + org) for org in ORG_NAMES):
                raise ProvisionError("Existing unrelated identity/namespace requires explicit review")
        env = os.environ.copy()
        env["TF_VAR_forgejo_api_token"] = api.token
        if state.strip():
            previous = json.loads(command(wrapper + ["output", "-json"], env=env))
            for org, expected_id in previous["namespace_ids"]["value"].items():
                current = api.request("GET", "/orgs/" + org)
                if not current or current["id"] != expected_id:
                    raise ProvisionError("Existing namespace identity changed; refusing adoption or recreation")
        for key in ["TF_LOG", "TF_LOG_PATH", "TF_LOG_PROVIDER", "TF_LOG_CORE"]:
            env.pop(key, None)
        with tempfile.TemporaryDirectory(prefix="forgejo-plan-", dir="/dev/shm") as directory:
            plan = str(Path(directory) / "plan")
            command(wrapper + ["plan", "-out=" + plan, "-input=false"], env=env)
            planned = json.loads(command(wrapper + ["show", "-json", plan], env=env))
            allowed = {"forgejo_user", "forgejo_organization", "forgejo_team", "forgejo_team_member"}
            for change in planned.get("resource_changes", []):
                if change.get("mode") != "data" and (change["type"] not in allowed or "delete" in change["change"]["actions"]):
                    raise ProvisionError("Provisioning plan exceeds approved scope")
            command(wrapper + ["apply", "-input=false", plan], env=env)
        outputs = json.loads(command(wrapper + ["output", "-json"], env=env))
        verify(api, outputs)
        token = vault_value(vault_read(vault, password_file), "forgejo_mirrors_token")
        if not token:
            existing = api.request("GET", "/users/forgejo-mirrors/tokens")
            if existing:
                raise ProvisionError("Untracked service token requires managed review")
            token = issue_token(cli, "forgejo-mirrors", "mirror-discovery-v1", SERVICE_SCOPES)
            vault_add(vault, password_file, "forgejo_mirrors_token", token)
        service = API("https://source.net.scetrov.live/api/v1", token)
        for org in ORG_NAMES:
            if service.request("GET", "/orgs/" + org)["id"] != outputs["namespace_ids"]["value"][org]:
                raise ProvisionError("Service credential does not match authorized namespaces")
    return outputs["namespace_ids"]["value"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Explicitly authorize permanent provisioning and temporary admin bootstrap")
    args = parser.parse_args()
    if not args.apply:
        parser.error("--apply is required; bootstrap is itself a privileged mutation")
    try:
        result = provision(ROOT / "src/secrets.yml", Path.home() / ".ansible/nixos_vault_password")
    except Exception:
        print("Forgejo provisioning failed; sensitive diagnostics suppressed. Verify bootstrap cleanup before retry.", file=sys.stderr)
        return 1
    print(json.dumps({"namespaceIds": result, "bootstrapRemoved": True, "importsEnabled": False}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
