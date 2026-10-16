"""Encrypt only the Hermes environment supplied on stdin; never persist plaintext.

Recipients come from the existing agenix policy. No private identity is needed
for encryption. Ansible supplies the vault-rendered input under no_log.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT / "src/roles/secrets/files/secrets"


def encrypt(content):
    recipients = json.loads(subprocess.check_output(
        ["nix-instantiate", "--eval", "--strict", "--json", "--expr",
         '(import ./secrets.nix)."hermes_webui_env.age".publicKeys'],
        cwd=SECRETS,
    ))
    if not recipients or not all(isinstance(key, str) and key for key in recipients):
        raise ValueError("Invalid Hermes agenix recipient policy")
    with tempfile.TemporaryDirectory(prefix=".hermes-encrypt-", dir=SECRETS) as directory:
        output = Path(directory) / "hermes_webui_env.age"
        # Armored ciphertext is safe for the repository's text-formatting hooks.
        command = ["age", "--encrypt", "--armor", "--output", str(output)]
        for recipient in recipients:
            command.extend(["--recipient", recipient])
        subprocess.run(command, input=content, check=True)
        output.chmod(0o600)
        os.replace(output, SECRETS / output.name)


if __name__ == "__main__":
    encrypt(sys.stdin.buffer.read())
