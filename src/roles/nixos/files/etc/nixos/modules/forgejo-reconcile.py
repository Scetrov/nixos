"""Reconcile native OIDC before Forgejo starts; never print captured CLI output.

The upstream OIDC CLI requires runtime secret argv (operator-accepted exception).
Other credentials must not use this exception. No bootstrap password is needed:
the signed owner-group claim grants administration on OIDC enrollment/sign-in.
"""

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys


class ReconcileError(Exception):
    pass


def credential(path):
    value = Path(path).read_text().strip()
    if not value or any(c.isspace() for c in value) or "placeholder" in value.lower():
        raise ReconcileError("Invalid OIDC runtime credential")
    return value


def run(command):
    # Never propagate CalledProcessError: its text contains the secret argv.
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=90)
    except (OSError, subprocess.SubprocessError):
        raise ReconcileError("OIDC administration command could not complete") from None
    if result.returncode:
        raise ReconcileError("OIDC administration command failed; output suppressed")
    return result.stdout


def source_id(output):
    matches = []
    for line in output.splitlines():
        match = re.fullmatch(r"\s*(\d+)\s+authentik\s+(\S+)\s+(true|false)\s*", line)
        if match:
            if match[2] != "OAuth2":
                raise ReconcileError("Existing authentik source has an unexpected type")
            matches.append(match[1])
    if len(matches) > 1:
        raise ReconcileError("Duplicate authentik sources; refusing ambiguous reconciliation")
    if "ID" not in output or "Enabled" not in output:
        raise ReconcileError("Unexpected authentication-source listing")
    return matches[0] if matches else None


def reconcile(binary, config, work_path, client_id_file, secret_file, discovery_url):
    client_id = credential(client_id_file)
    secret = credential(secret_file)
    base = [binary, "--config", config, "--work-path", work_path, "admin", "auth"]
    existing = source_id(run([*base, "list"]))
    command = [*base, "update-oauth", "--id", existing] if existing else [*base, "add-oauth"]
    command += [
        "--name", "authentik", "--provider", "openidConnect",
        "--key", client_id, "--secret", secret,
        "--auto-discover-url", discovery_url,
        "--scopes", "openid", "--scopes", "profile", "--scopes", "email",
        "--required-claim-name", "groups", "--required-claim-value", "Forgejo Owners",
        "--group-claim-name", "groups", "--admin-group", "Forgejo Owners",
    ]
    # Updating preserves intentional source disablement; do not undo revocation.
    run(command)
    if source_id(run([*base, "list"])) is None:
        raise ReconcileError("OIDC source missing after reconciliation")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--work-path", required=True)
    parser.add_argument("--discovery-url", required=True)
    args = parser.parse_args()
    try:
        credentials = Path(os.environ["CREDENTIALS_DIRECTORY"])
        reconcile(args.binary, args.config, args.work_path,
                  credentials / "forgejo_oidc_client_id",
                  credentials / "forgejo_oidc_client_secret", args.discovery_url)
    except (ReconcileError, OSError, KeyError):
        print("Forgejo OIDC reconciliation failed; sensitive diagnostics suppressed", file=sys.stderr)
        return 1
    print("Forgejo OIDC source reconciled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
