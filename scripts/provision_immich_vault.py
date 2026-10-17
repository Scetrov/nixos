#!/usr/bin/env python3
"""Provision the operator-approved Immich recovery identity in encrypted Vault.

Run with operator authorization outside the sandbox. Plaintext stays in captured
pipes and memory; only ciphertext is written to disk. Never rotate implicitly.
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


def provision(vault: Path, password_file: Path) -> bool:
    plaintext = subprocess.run(
        ["ansible-vault", "view", str(vault), "--vault-password-file", str(password_file)],
        capture_output=True, check=True, text=True,
    ).stdout
    values = yaml.safe_load(plaintext)
    if not isinstance(values, dict):
        raise ValueError("invalid vault mapping")
    email = values.get("immich_admin_email", "git@scetrov.live")
    password = values.get("immich_admin_password")
    if email != "git@scetrov.live":
        raise ValueError("unexpected recovery identity")
    if "immich_admin_password" in values and (
        not isinstance(password, str) or len(password) < 32
        or password.strip().lower().endswith("_placeholder")
    ):
        raise ValueError("invalid existing recovery password")
    additions = {}
    if "immich_admin_email" not in values:
        additions["immich_admin_email"] = email
    if "immich_admin_password" not in values:
        additions["immich_admin_password"] = secrets.token_hex(32)
    if not additions:
        return False
    updated = plaintext.rstrip() + "\n" + "".join(
        key + ": " + json.dumps(value) + "\n" for key, value in additions.items()
    )
    fd, name = tempfile.mkstemp(prefix=".immich-vault-", dir=vault.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        subprocess.run(
            ["ansible-vault", "encrypt", "--output", str(temporary), "--vault-password-file", str(password_file)],
            input=updated, capture_output=True, check=True, text=True,
        )
        if not temporary.read_bytes().startswith(b"$ANSIBLE_VAULT;"):
            raise ValueError("invalid encrypted output")
        temporary.chmod(0o600)
        temporary.replace(vault)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        changed = provision(root / "src/secrets.yml", Path.home() / ".ansible/nixos_vault_password")
    except (OSError, ValueError, yaml.YAMLError, subprocess.CalledProcessError):
        print("Immich Vault provisioning failed; no credential details disclosed.", file=sys.stderr)
        return 1
    print("Immich Vault recovery identity: " + ("created" if changed else "already present"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
