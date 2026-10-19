#!/usr/bin/env python3
"""Provision the approved Dependency-Track SBOM target and upload team.

Creates or reuses one named project/version, a BOM_UPLOAD team, and that team's
project ACL mapping. An API key is created only when portfolio ACL is already
enabled, the team has no key, and the vault has no collector token. The key is
written into the encrypted vault and is never printed.

Exit 0: target ready and a vault token exists.
Exit 2: target exists, but ACL is off so no upload key was issued.
Exit 1: provisioning failed; no credential details are disclosed.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def request(base: str, token: str, path: str, method: str = "GET", body=None, ok=(200,)):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read(1024 * 1024)
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read(4096)
        status = exc.code
    if status not in ok:
        raise RuntimeError(f"dependency_track_http_{status}")
    if not raw or status == 404:
        return status, None
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("dependency_track_non_json") from exc


def vault_has_token(vault: Path, password_file: Path) -> bool:
    view = subprocess.run(
        ["ansible-vault", "view", str(vault), "--vault-password-file", str(password_file)],
        capture_output=True, check=True, text=True,
    ).stdout
    values = yaml.safe_load(view)
    if not isinstance(values, dict):
        raise RuntimeError("invalid_vault")
    value = values.get("dtrack_sbom_collector_token", "")
    return isinstance(value, str) and len(value.strip()) >= 16 and not value.lower().endswith("_placeholder")


def store_token(vault: Path, password_file: Path, token: str) -> None:
    view = subprocess.run(
        ["ansible-vault", "view", str(vault), "--vault-password-file", str(password_file)],
        capture_output=True, check=True, text=True,
    ).stdout
    values = yaml.safe_load(view)
    if not isinstance(values, dict):
        raise RuntimeError("invalid_vault")
    if "dtrack_sbom_collector_token" in values:
        raise RuntimeError("refusing_to_rotate_existing_token")
    updated = view.rstrip() + "\ndtrack_sbom_collector_token: " + json.dumps(token) + "\n"
    fd, name = tempfile.mkstemp(prefix=".sbom-vault-", dir=vault.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        subprocess.run(
            ["ansible-vault", "encrypt", "--output", str(temporary), "--vault-password-file", str(password_file)],
            input=updated, capture_output=True, check=True, text=True,
        )
        if not temporary.read_bytes().startswith(b"$ANSIBLE_VAULT;"):
            raise RuntimeError("vault_encryption_failed")
        temporary.chmod(0o600)
        temporary.replace(vault)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    base = os.environ["DT_URL"].rstrip("/")
    admin = os.environ["DT_ADMIN_TOKEN"]
    name = os.environ.get("DT_PROJECT_NAME", "efctl")
    version = os.environ.get("DT_PROJECT_VERSION", "main")
    team_name = os.environ.get("DT_TEAM_NAME", "sbom-collector")
    enable_acl = os.environ.get("DT_ENABLE_ACL") == "1"
    vault = Path(os.environ.get("DT_VAULT", ROOT / "src/secrets.yml"))
    password_file = Path(os.environ.get("DT_VAULT_PASSWORD_FILE", Path.home() / ".ansible/nixos_vault_password"))
    evidence = Path(os.environ["DT_EVIDENCE_PATH"]) if os.environ.get("DT_EVIDENCE_PATH") else None
    changed = False
    try:
        lookup = urllib.parse.urlencode({"name": name, "version": version})
        status, project = request(base, admin, "/api/v1/project/lookup?" + lookup, ok=(200, 404))
        if status == 404:
            _, project = request(base, admin, "/api/v1/project", "PUT", {
                "name": name, "version": version, "classifier": "APPLICATION", "active": True,
            }, ok=(200, 201))
            changed = True
        project_uuid = str(project["uuid"])
        _, teams = request(base, admin, "/api/v1/team")
        team = next((item for item in teams if item.get("name") == team_name), None)
        if team is None:
            _, team = request(base, admin, "/api/v1/team", "PUT", {"name": team_name}, ok=(200, 201))
            changed = True
        team_uuid = str(team["uuid"])
        permissions = {item.get("name") for item in team.get("permissions") or []}
        if "BOM_UPLOAD" not in permissions:
            request(base, admin, f"/api/v1/permission/BOM_UPLOAD/team/{team_uuid}", "POST", ok=(200, 201, 304, 409))
            changed = True
        _, mapped = request(base, admin, f"/api/v1/acl/team/{team_uuid}")
        mapped_ids = {item.get("uuid") for item in mapped or []}
        if project_uuid not in mapped_ids:
            request(base, admin, "/api/v1/acl/mapping", "PUT", {
                "team": team_uuid, "project": project_uuid,
            }, ok=(200, 201, 409))
            changed = True
        _, properties = request(base, admin, "/api/v1/configProperty", ok=(200,))
        acl = next((
            item for item in properties or []
            if item.get("groupName") == "access-management" and item.get("propertyName") == "acl.enabled"
        ), None)
        acl_on = isinstance(acl, dict) and str(acl.get("propertyValue", "")).lower() == "true"
        if not acl_on and enable_acl:
            if not isinstance(acl, dict):
                raise RuntimeError("acl_property_missing")
            acl["propertyValue"] = "true"
            request(base, admin, "/api/v1/configProperty", "POST", acl, ok=(200, 201))
            acl_on = True
            changed = True
        token_state = "present" if vault_has_token(vault, password_file) else "absent"
        if acl_on and token_state == "absent":
            if team.get("apiKeys"):
                token_state = "team_has_unrecorded_key"
            else:
                _, created = request(base, admin, f"/api/v1/team/{team_uuid}/key", "PUT", ok=(200, 201))
                key = created.get("key") if isinstance(created, dict) else None
                if not isinstance(key, str) or len(key) < 16 or "\n" in key:
                    raise RuntimeError("api_key_missing")
                store_token(vault, password_file, key)
                token_state = "created"
                changed = True
        status_name = "ready" if acl_on and token_state in {"present", "created"} else "blocked"
        result = {
            "status": status_name,
            "changed": changed,
            "project": name,
            "version": version,
            "project_uuid": project_uuid,
            "team": team_name,
            "acl": "enabled" if acl_on else "disabled",
            "token": token_state,
        }
        if evidence:
            evidence.write_text(json.dumps({k: v for k, v in result.items() if k != "changed"}, indent=2) + "\n")
            evidence.chmod(0o644)
        print(json.dumps(result))
        return 0 if status_name == "ready" else 2
    except Exception:
        print(json.dumps({"status": "failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
