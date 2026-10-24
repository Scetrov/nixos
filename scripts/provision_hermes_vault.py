#!/usr/bin/env python3
"""Add only the absent optional local-Qwen field to encrypted Ansible Vault.

Existing values are preserved. Plaintext stays in captured pipes, not files,
arguments or logs. This does not provision subscription tokens or invent keys.
"""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import yaml


FIELD = "hermes_local_qwen_api_key"


def provision(vault, password_file):
    view = subprocess.run(
        ["ansible-vault", "view", str(vault), "--vault-password-file", str(password_file)],
        capture_output=True, check=True, text=True,
    ).stdout
    values = yaml.safe_load(view)
    if not isinstance(values, dict):
        raise ValueError("invalid vault mapping")
    if FIELD in values:
        if not isinstance(values[FIELD], str):
            raise ValueError("local Qwen key must be a string")
        return False
    updated = view.rstrip() + '\n' + FIELD + ': ""\n'
    if yaml.safe_load(updated) != {**values, FIELD: ""}:
        raise ValueError("vault update did not preserve existing entries")
    fd, name = tempfile.mkstemp(prefix=".hermes-vault-", dir=vault.parent)
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=Path(__file__).resolve().parents[1] / "src/secrets.yml")
    parser.add_argument("--password-file", type=Path, default=Path.home() / ".ansible/nixos_vault_password")
    args = parser.parse_args()
    try:
        changed = provision(args.vault, args.password_file)
    except (OSError, ValueError, yaml.YAMLError, subprocess.CalledProcessError):
        print("Hermes Vault preparation failed; no credential details disclosed.", file=sys.stderr)
        return 1
    print("Hermes optional local-key field: " + ("created empty" if changed else "already present; preserved"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
