#!/usr/bin/env python3
"""Provision/reuse a dedicated SFTP publisher key in Ansible Vault, never stdout."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

import yaml


def provision(root: Path) -> None:
    vault = root / "src/secrets.yml"
    password = Path.home() / ".ansible/nixos_vault_password"
    original = vault.read_bytes()
    plaintext = subprocess.run(
        ["ansible-vault", "view", str(vault), "--vault-password-file", str(password)],
        capture_output=True, check=True).stdout.decode()
    values = yaml.safe_load(plaintext)
    with tempfile.TemporaryDirectory(prefix="xrdp-publisher-") as temporary:
        key = Path(temporary) / "identity"
        if values.get("xrdp_crl_publisher_key"):
            key.write_text(values["xrdp_crl_publisher_key"])
            key.chmod(0o600)
        else:
            subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "",
                            "-C", "xrdp-crl-publisher", "-f", str(key)],
                           check=True, capture_output=True)
            plaintext = plaintext.rstrip() + "\n\nxrdp_crl_publisher_key: |\n"
            plaintext += "".join("  " + line + "\n" for line in key.read_text().splitlines())
            encrypted = Path(temporary) / "vault"
            encrypted.write_text(plaintext)
            encrypted.chmod(0o600)
            subprocess.run(["ansible-vault", "encrypt", str(encrypted),
                            "--vault-password-file", str(password)],
                           check=True, capture_output=True)
            if hashlib.sha256(vault.read_bytes()).digest() != hashlib.sha256(original).digest():
                raise RuntimeError("Vault changed concurrently; refusing replacement")
            # Same-filesystem replacement; only ciphertext is written in the repo.
            destination = vault.with_suffix(".yml.next")
            try:
                destination.write_bytes(encrypted.read_bytes())
                destination.chmod(0o600)
                os.replace(destination, vault)
            finally:
                destination.unlink(missing_ok=True)
        public = subprocess.run(["ssh-keygen", "-y", "-f", str(key)],
                                check=True, capture_output=True).stdout.decode().strip()
        path = root / "src/roles/nixos/files/etc/nixos/modules/xrdp-crl-publisher.pub"
        path.write_text(public + "\n")
        path.chmod(0o644)


if __name__ == "__main__":
    os.umask(0o077)
    try:
        provision(Path(__file__).resolve().parents[1])
    except Exception:
        raise SystemExit("Publisher provisioning failed; secret diagnostics suppressed.")
    print("Vault-backed publisher identity and public key are ready.")
