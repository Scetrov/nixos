#!/usr/bin/env python3
"""Authentik machine-token exchange and Minecraft Vault persistence.

The native Garage automation token is never an input or output of this program.
Stdout is either a machine JWT, the sentinel ``disabled``, or a short status.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BROKER_USERNAME = "garage-admin-broker"
TOKEN_URL = "https://identity.net.scetrov.live/application/o/token/"
ADMIN_API = "https://garage-admin.net.scetrov.live"
BUCKET_ALIAS = "minecraft"
KEY_NAME = "minecraft-backup"
BUCKET_ADDRESS = "garage_bucket.minecraft[0]"
KEY_ADDRESS = "garage_key.minecraft[0]"
ACCESS_KEY_NAME = "garage_minecraft_access_key_id"
SECRET_KEY_NAME = "garage_minecraft_secret_access_key"
ADMIN_TOKEN_NAME = "garage_admin_automation_token"
ADMIN_TOKEN_PATTERN = re.compile(r"^[0-9a-f]{16,64}\.[A-Za-z0-9_-]{16,}$")
DISABLED = "disabled"


class BrokerError(Exception):
    """Fail closed without embedding credential material."""


def _open(opener, request):
    if opener is None:
        return urllib.request.urlopen(request, timeout=30)
    return opener.open(request, timeout=30)


def _extract(text: str, key: str) -> str:
    prefix = key + ":"
    lines = text.splitlines()
    for index, raw in enumerate(lines):
        if not raw.startswith(prefix):
            continue
        value = raw[len(prefix):].strip()
        if value == "|":
            block = []
            for extra in lines[index + 1:]:
                if extra.startswith("  "):
                    block.append(extra[2:])
                elif extra.strip() == "":
                    block.append("")
                else:
                    break
            return "\n".join(block).strip()
        if value.startswith('"'):
            parsed = json.loads(value)
            if not isinstance(parsed, str):
                raise BrokerError("vault credential has an invalid type")
            return parsed
        return value.strip("'").strip('"')
    return ""


def _vault_text(vault: Path, password_file: Path) -> str:
    result = subprocess.run(
        ["ansible-vault", "view", str(vault), "--vault-password-file", str(password_file)],
        capture_output=True, check=False, text=True,
    )
    if result.returncode != 0:
        raise BrokerError("unable to read vault")
    return result.stdout


def _write_vault(vault: Path, password_file: Path, plaintext: str) -> None:
    fd, name = tempfile.mkstemp(prefix=".garage-vault-", dir=vault.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        result = subprocess.run(
            ["ansible-vault", "encrypt", "--output", str(temporary), "--vault-password-file", str(password_file)],
            input=plaintext, capture_output=True, check=False, text=True,
        )
        if result.returncode != 0 or not temporary.read_bytes().startswith(b"$ANSIBLE_VAULT;"):
            raise BrokerError("vault encryption failed")
        temporary.chmod(0o600)
        temporary.replace(vault)
    finally:
        temporary.unlink(missing_ok=True)


def exchange_token(client_id: str, password: str, opener=None) -> str:
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "username": BROKER_USERNAME,
        "password": password,
        "scope": "openid profile",
    }).encode()
    request = urllib.request.Request(
        TOKEN_URL, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    try:
        with _open(opener, request) as response:
            payload = json.loads(response.read().decode())
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise BrokerError("Authentik machine-token exchange failed") from exc
    token = payload.get("access_token") if isinstance(payload, dict) else None
    if not isinstance(token, str) or token.count(".") < 2:
        raise BrokerError("Authentik did not return a machine JWT")
    return token


def _items(payload: object) -> list:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("buckets", "keys", "items"):
            if isinstance(payload.get(key), list):
                return payload[key]
    raise BrokerError("Garage admin list response was not understood")


def _get_json(url: str, token: str, opener=None) -> object:
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + token, "Accept": "application/json"})
    try:
        with _open(opener, request) as response:
            return json.loads(response.read().decode())
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise BrokerError("Garage admin preflight failed") from exc


def _aliases(item: dict) -> set[str]:
    found = set()
    for key in ("globalAliases", "global_aliases", "globalAlias", "global_alias"):
        raw = item.get(key)
        if isinstance(raw, str):
            found.add(raw)
        elif isinstance(raw, list):
            found.update(value for value in raw if isinstance(value, str))
    return found


def ownership_conflict(buckets: object, keys: object, state_addresses: set[str]) -> str | None:
    for item in _items(buckets):
        if isinstance(item, dict) and BUCKET_ALIAS in _aliases(item) and BUCKET_ADDRESS not in state_addresses:
            return "existing minecraft bucket requires ownership review before adoption"
    for item in _items(keys):
        if isinstance(item, dict) and item.get("name") == KEY_NAME and KEY_ADDRESS not in state_addresses:
            return "existing minecraft key requires ownership review before adoption"
    return None


def prepare(generated_text: str, state_addresses: set[str], opener=None) -> str:
    if not generated_text.strip():
        return DISABLED
    client_id = _extract(generated_text, "garage_admin_broker_client_id")
    password = _extract(generated_text, "garage_admin_broker_app_password")
    if client_id == "" and password == "":
        return DISABLED
    if client_id == "" or password == "":
        raise BrokerError("incomplete Garage broker credential")
    token = exchange_token(client_id, password, opener=opener)
    conflict = ownership_conflict(
        _get_json(ADMIN_API + "/v2/ListBuckets", token, opener),
        _get_json(ADMIN_API + "/v2/ListKeys", token, opener),
        state_addresses,
    )
    if conflict:
        raise BrokerError(conflict)
    return token


def _pair(outputs: dict) -> tuple[str, str] | None:
    access = outputs.get("garage_minecraft_access_key_id", {}).get("value")
    secret = outputs.get("garage_minecraft_secret_access_key", {}).get("value")
    if access in (None, "") and secret in (None, ""):
        return None
    if not isinstance(access, str) or not isinstance(secret, str) or access.strip() == "" or secret.strip() == "":
        raise BrokerError("Garage credential output is incomplete")
    return access.strip(), secret.strip()


def persist_pair(vault: Path, password_file: Path, outputs: dict) -> str:
    pair = _pair(outputs)
    if pair is None:
        return "absent"
    access, secret = pair
    current = _vault_text(vault, password_file)
    existing = (_extract(current, ACCESS_KEY_NAME), _extract(current, SECRET_KEY_NAME))
    if existing == ("", ""):
        updated = current.rstrip() + "\n" + ACCESS_KEY_NAME + ": " + json.dumps(access) + "\n" + SECRET_KEY_NAME + ": " + json.dumps(secret) + "\n"
        _write_vault(vault, password_file, updated)
        return "created"
    if existing == (access, secret):
        return "unchanged"
    raise BrokerError("Vault already holds a different Minecraft pair; refusing to rotate")


def persist_admin_token(vault: Path, password_file: Path, payload: dict) -> str:
    token = payload.get("secretToken") if isinstance(payload, dict) else None
    if not isinstance(token, str) or ADMIN_TOKEN_PATTERN.fullmatch(token) is None:
        raise BrokerError("Garage did not return a scoped automation token")
    current = _vault_text(vault, password_file)
    existing = _extract(current, ADMIN_TOKEN_NAME)
    if existing == token:
        return "unchanged"
    if existing != "":
        raise BrokerError("Vault already holds a different Garage automation token")
    updated = current.rstrip() + "\n" + ADMIN_TOKEN_NAME + ": " + json.dumps(token) + "\n"
    _write_vault(vault, password_file, updated)
    return "created"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "persist-pair", "persist-admin-token"))
    parser.add_argument("--generated", type=Path)
    parser.add_argument("--vault", type=Path, default=Path(__file__).resolve().parents[1] / "src/secrets.yml")
    parser.add_argument("--password-file", type=Path, default=Path.home() / ".ansible/nixos_vault_password")
    parser.add_argument("--state-list", default="")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            text = args.generated.read_text(encoding="utf-8") if args.generated and args.generated.is_file() else ""
            print(prepare(text, {line.strip() for line in args.state_list.splitlines() if line.strip()}))
            return 0
        payload = json.load(sys.stdin)
        if args.command == "persist-pair":
            print(persist_pair(args.vault, args.password_file, payload))
        else:
            print(persist_admin_token(args.vault, args.password_file, payload))
    except BrokerError as exc:
        print("garage-broker: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
