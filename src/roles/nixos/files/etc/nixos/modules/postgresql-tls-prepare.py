#!/usr/bin/env python3
"""Validate and atomically publish only the shared PostgreSQL certificate pair.

The caller serializes publication AND reload using the same systemd oneshot.
Never log subprocess diagnostics (they may include certificate/key filenames).
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile


HOSTNAMES = ("habiki.net.scetrov.live", "postgres.net.scetrov.live")


def publish(source: Path, target: Path, ca: Path, openssl: str,
            uid: int = 0, gid: int = 70) -> None:
    target.mkdir(mode=0o750, parents=True, exist_ok=True)
    os.chown(target, uid, gid)
    target.chmod(0o750)
    stage = Path(tempfile.mkdtemp(prefix="pair-", dir=target))
    link = target / ".next"
    published = False
    try:
        os.chown(stage, uid, gid)
        for name, mode in (("fullchain.pem", 0o644), ("key.pem", 0o640)):
            path = stage / name
            # mkdtemp is 0700 until BOTH files have their final permissions.
            shutil.copyfile(source / name, path)
            os.chown(path, uid, gid)
            path.chmod(mode)
        ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER).load_cert_chain(
            stage / "fullchain.pem", stage / "key.pem")
        for hostname in HOSTNAMES:
            subprocess.run(
                [openssl, "verify", "-purpose", "sslserver", "-CAfile", str(ca),
                 "-untrusted", str(stage / "fullchain.pem"),
                 "-verify_hostname", hostname, str(stage / "fullchain.pem")],
                check=True, capture_output=True, timeout=15,
            )
        stage.chmod(0o750)
        link.unlink(missing_ok=True)
        link.symlink_to(stage.name, target_is_directory=True)
        os.replace(link, target / "current")
        published = True
        # Retain the preceding pair for explicit operator recovery; do not prune
        # generations here or implement automatic rollback after reload failure.
    finally:
        link.unlink(missing_ok=True)
        if not published:
            shutil.rmtree(stage)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--ca", type=Path, required=True)
    parser.add_argument("--openssl", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        publish(args.source, args.target, args.ca, args.openssl)
    except (OSError, ValueError, ssl.SSLError, subprocess.SubprocessError):
        print("PostgreSQL TLS preparation failed; working pair not replaced.")
        return 1
    print("Validated PostgreSQL TLS certificate pair published.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
