#!/usr/bin/env python3
"""Renew Bullit's CA-signed XRDP certificate; never fall back to self-signing."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile


HOSTNAMES = ("bullit", "bullit.net.scetrov.live")
IP_ADDRESS = "10.229.10.10"


def renew(target: Path, ca: Path, ca_key: Path, openssl: str,
          gid: int, renew_before: int = 30 * 86400) -> bool:
    def run(*args: str) -> bytes:
        return subprocess.run([openssl, *args], check=True, capture_output=True,
                              timeout=60).stdout

    def validate(pair: Path) -> None:
        ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER).load_cert_chain(
            pair / "cert.pem", pair / "key.pem")
        for name in HOSTNAMES:
            run("verify", "-purpose", "sslserver", "-CAfile", str(ca),
                "-verify_hostname", name, str(pair / "cert.pem"))
        run("verify", "-purpose", "sslserver", "-CAfile", str(ca),
            "-verify_ip", IP_ADDRESS, str(pair / "cert.pem"))
        run("x509", "-in", str(pair / "cert.pem"), "-noout", "-checkend",
            str(renew_before))

    # Do not keep issuing leaves when the trust anchor is near expiry.
    run("x509", "-in", str(ca), "-noout", "-checkend", str(366 * 86400))
    current = target / "current"
    try:
        validate(current)
        if (current / "ca.pem").read_bytes() == ca.read_bytes():
            return False
    except (OSError, ValueError, ssl.SSLError, subprocess.SubprocessError):
        pass  # Invalid/expiring leaf: prepare a replacement before touching it.

    target.mkdir(mode=0o750, parents=True, exist_ok=True)
    os.chown(target, os.getuid(), gid)
    target.chmod(0o750)
    stage = Path(tempfile.mkdtemp(prefix="pair-", dir=target))
    link = target / ".next"
    published = False
    try:
        extensions = stage / "extensions.cnf"
        extensions.write_text(
            "basicConstraints=critical,CA:FALSE\n"
            "keyUsage=critical,digitalSignature,keyEncipherment\n"
            "extendedKeyUsage=serverAuth\n"
            "subjectKeyIdentifier=hash\n"
            "authorityKeyIdentifier=keyid,issuer\n"
            f"subjectAltName=DNS:{HOSTNAMES[0]},DNS:{HOSTNAMES[1]},IP:{IP_ADDRESS}\n"
        )
        run("req", "-new", "-newkey", "rsa:3072", "-nodes", "-sha256",
            "-subj", f"/CN={HOSTNAMES[1]}", "-keyout", str(stage / "key.pem"),
            "-out", str(stage / "request.pem"))
        # Random serial: no mutable CA database or serial file beside agenix keys.
        serial = run("rand", "-hex", "16").decode().strip()
        run("x509", "-req", "-in", str(stage / "request.pem"),
            "-CA", str(ca), "-CAkey", str(ca_key), "-set_serial", f"0x{serial}",
            "-days", "365", "-sha256", "-extfile", str(extensions),
            "-out", str(stage / "cert.pem"))
        validate(stage)
        shutil.copyfile(ca, stage / "ca.pem")
        extensions.unlink()
        (stage / "request.pem").unlink()
        for name, mode in (("key.pem", 0o640), ("cert.pem", 0o644), ("ca.pem", 0o644)):
            path = stage / name
            os.chown(path, os.getuid(), gid)
            path.chmod(mode)
        os.chown(stage, os.getuid(), gid)
        stage.chmod(0o750)
        link.unlink(missing_ok=True)
        link.symlink_to(stage.name, target_is_directory=True)
        os.replace(link, current)
        published = True
        # Keep only the current and preceding generation, never unbounded keys.
        generations = sorted(target.glob("pair-*"), key=lambda p: p.stat().st_mtime,
                             reverse=True)
        previous = next((p for p in generations if p != stage), None)
        for old in generations:
            if old not in (stage, previous):
                shutil.rmtree(old)
        return True
    finally:
        link.unlink(missing_ok=True)
        if not published:
            shutil.rmtree(stage)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--ca", type=Path, required=True)
    parser.add_argument("--ca-key", type=Path, required=True)
    parser.add_argument("--openssl", required=True)
    parser.add_argument("--group", required=True)
    args = parser.parse_args()
    import grp
    os.umask(0o077)
    try:
        changed = renew(args.target, args.ca, args.ca_key, args.openssl,
                        grp.getgrnam(args.group).gr_gid)
    except (OSError, ValueError, ssl.SSLError, subprocess.SubprocessError):
        print("XRDP TLS renewal failed; working certificate pair not replaced.")
        return 1
    print("renewed" if changed else "Certificate is current; no renewal needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
