#!/usr/bin/env python3
"""Render secret-bearing Quantum configuration only into protected runtime files."""

import argparse
import json
import os
from pathlib import Path
import pwd
import sys

if __package__:
    from .filebrowser_host import prepare
else:
    from filebrowser_host import prepare


def runtime_config(enrollments, client_id, client_secret, port, machine_public_key=None):
    if not client_id or not client_secret or not (1 <= port <= 65535):
        raise ValueError("Invalid runtime inputs")
    config = {
        "http": {
            "listen": "0.0.0.0",
            "port": 8080,
            "externalUrl": "https://files.net.scetrov.live",
            "trustProxyHeaders": True,
            "disableWebDAV": True,
        },
        "server": {
            "database": {"path": "/state/quantum.sqlite", "activity": {"disabled": True}},
            "cacheDir": "/state/cache",
            # Group-class write is required for inherited named-user ACL masks.
            "filesystem": {"createFilePermission": "660", "createDirectoryPermission": "770"},
            "sources": [
                {"name": entry["unix_username"], "path": "/documents/" + entry["unix_username"], "config": {"private": True, "defaultEnabled": False}}
                for entry in enrollments
            ],
            # Semantic activity logs include filenames; leave them disabled.
            "logging": [{"levels": "warning|error", "apiFilter": "disabled"}],
        },
        "auth": {
            "methods": {
                "password": {"enabled": False, "signup": False},
                "oidc": {
                    "enabled": True,
                    "issuerUrl": "https://identity.net.scetrov.live/application/o/filebrowser/",
                    "clientId": client_id,
                    "clientSecret": client_secret,
                    "userIdentifier": "preferred_username",
                    # Ordinary authorization is enforced by Authentik UUID policy.
                    # No ordinary group grants Quantum administration.
                    "adminGroup": "",
                },
            },
        },
        "userDefaults": {"account": {"permissions": {"admin": False, "api": False, "share": False, "realtime": False}}},
    }
    if machine_public_key is not None:
        if "PRIVATE KEY" in machine_public_key or not any(marker in machine_public_key for marker in ("BEGIN CERTIFICATE", "BEGIN PUBLIC KEY")):
            raise ValueError("Machine verification requires a public certificate/key")
        config["auth"]["methods"]["jwt"] = {
            "enabled": True,
            "secret": machine_public_key,
            "algorithm": "RS256",
            "header": "X-Filebrowser-Admin-Assertion",
            "userIdentifier": "filebrowser_machine_username",
            "groupsClaim": "filebrowser_machine_groups",
            "userGroups": ["filebrowser-reconciler"],
            "adminGroup": "filebrowser-reconciler",
        }
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enrollments", required=True)
    parser.add_argument("--port", type=int, default=8092)
    args = parser.parse_args()
    try:
        if os.geteuid() != 0:
            raise ValueError("Root runtime preparation required")
        run = Path("/run/filebrowser")
        run.mkdir(mode=0o755, exist_ok=True)
        # Fail closed on every start/reconciliation. Only the verified scope
        # reconciler may publish readiness for Caddy.
        (run / "ready").unlink(missing_ok=True)
        state = prepare(json.loads(Path(args.enrollments).read_text()), "/var/lib/filebrowser-enrollment", "filebrowser", create_missing=True)
        service = pwd.getpwnam("filebrowser")
        mounts = run / "mounts"
        mounts.mkdir(mode=0o700, exist_ok=True)
        for entry in state["enrollments"]:
            link = mounts / entry["unix_username"]
            if link.is_symlink():
                link.unlink()
            elif link.exists():
                raise ValueError("Unexpected mount-slot object")
            # Root-controlled indirection gives NixOS stable mount slots while
            # binding the actual NSS-configured Documents path, not /home guesses.
            link.symlink_to(entry["documents"])
        credentials = Path(os.environ["CREDENTIALS_DIRECTORY"])
        config = runtime_config(state["enrollments"], (credentials / "oidc-client-id").read_text().strip(), (credentials / "oidc-client-secret").read_text().strip(), args.port, (credentials / "machine-public-key").read_text().strip())
        target = run / "config.yaml"
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o400)
        os.fchown(fd, service.pw_uid, service.pw_gid)
        os.fchmod(fd, 0o400)
        with os.fdopen(fd, "w") as stream:
            # JSON is valid YAML; use a .yaml name for Quantum's file combiner.
            json.dump(config, stream)
        print("Private Quantum runtime configuration prepared")
    except Exception:
        print("Quantum runtime preparation failed; route remains unavailable", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
