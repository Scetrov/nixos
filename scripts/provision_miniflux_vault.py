#!/usr/bin/env python3
"""Idempotently add Miniflux's database password to the existing Ansible Vault.

Plaintext is passed through captured pipes only, never arguments, files or logs.
Run outside the command sandbox with explicit operator authorization.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


def provision(vault: Path, password_file: Path) -> bool:
    view = subprocess.run(
        ["ansible-vault", "view", str(vault), "--vault-password-file", str(password_file)],
        capture_output=True, check=True, text=True,
    ).stdout
    values = yaml.safe_load(view)
    if not isinstance(values, dict):
        raise ValueError("invalid vault mapping")
    if "miniflux_db_password" in values:
        value = values["miniflux_db_password"]
        if not isinstance(value, str) or len(value.strip()) < 32 or value.lower().endswith("_placeholder"):
            raise ValueError("invalid existing Miniflux password")
        return False
    updated = view.rstrip() + "\nminiflux_db_password: " + json.dumps(secrets.token_hex(32)) + "\n"
    # The temporary output is encrypted by ansible-vault; plaintext stays in pipes.
    fd, name = tempfile.mkstemp(prefix=".miniflux-vault-", dir=vault.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        subprocess.run(
            ["ansible-vault", "encrypt", "--output", str(temporary), "--vault-password-file", str(password_file)],
            input=updated, capture_output=True, check=True, text=True,
        )
        if not temporary.read_bytes().startswith(b"$ANSIBLE_VAULT;"):
            raise ValueError("encryption did not produce a vault")
        temporary.chmod(0o600)
        temporary.replace(vault)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=Path(__file__).resolve().parents[1] / "src/secrets.yml")
    parser.add_argument("--password-file", type=Path, default=Path.home() / ".ansible/nixos_vault_password")
    args = parser.parse_args()
    try:
        changed = provision(args.vault, args.password_file)
    except (OSError, ValueError, yaml.YAMLError, subprocess.CalledProcessError):
        print("Miniflux Vault provisioning failed; no credential details disclosed.", file=sys.stderr)
        return 1
    print("Miniflux Vault credential: " + ("created" if changed else "already present"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
