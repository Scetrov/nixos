#!/usr/bin/env python3
"""Check public CRL and key-free recovery artifacts; emit Alloy textfile metrics."""
import argparse
import os
from pathlib import Path
import ssl
import subprocess
import tempfile
import time


def inspect(directory: Path, ca: Path, openssl: str, ssh_keygen: str, public_key: Path) -> dict:
    crl = directory / "bullit-xrdp.crl"
    if crl.is_symlink() or not crl.is_file() or crl.stat().st_size > 1024 * 1024:
        raise ValueError("CRL missing or invalid file type/size")
    result = subprocess.run(
        [openssl, "crl", "-inform", "DER", "-in", str(crl), "-verify", "-CAfile", str(ca),
         "-noout", "-lastupdate", "-nextupdate"], check=True, capture_output=True, timeout=15)
    dates = dict(line.split("=", 1) for line in result.stdout.decode().splitlines() if "=" in line)
    start = ssl.cert_time_to_seconds(dates["lastUpdate"])
    end = ssl.cert_time_to_seconds(dates["nextUpdate"])
    now = time.time()
    if not start <= now < end or end - start > 8 * 86400:
        raise ValueError("CRL outside allowed validity window")
    backups = [p for p in directory.glob("state-*.tar.gz") if p.is_file() and not p.is_symlink()]
    if not backups:
        raise ValueError("No recovery backup published")
    latest = max(backups, key=lambda p: p.stat().st_mtime)
    if latest.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Recovery backup exceeds size limit")
    signature = Path(str(latest) + ".sig")
    if signature.is_symlink() or not signature.is_file():
        raise ValueError("Recovery backup signature missing")
    with tempfile.TemporaryDirectory() as temporary:
        allowed = Path(temporary) / "allowed_signers"
        allowed.write_text("xrdp-crl-publisher " + public_key.read_text().strip() + "\n")
        subprocess.run([ssh_keygen, "-Y", "verify", "-f", str(allowed),
                        "-I", "xrdp-crl-publisher", "-n", "xrdp-pki-state",
                        "-s", str(signature)], input=latest.read_bytes(), check=True,
                       capture_output=True, timeout=30)
    return {"valid": 1, "next_update_timestamp_seconds": end,
            "backup_timestamp_seconds": latest.stat().st_mtime}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--openssl", required=True)
    parser.add_argument("--ssh-keygen", required=True)
    parser.add_argument("--publisher-public-key", type=Path, required=True)
    parser.add_argument("--directory", type=Path, default=Path("/var/lib/xrdp-crl/upload"))
    parser.add_argument("--ca", type=Path, default=Path("/var/lib/xrdp-crl/ca.crt"))
    parser.add_argument("--metrics", type=Path, default=Path("/var/lib/xrdp-crl-metrics"))
    args = parser.parse_args()
    values = {"valid": 0, "next_update_timestamp_seconds": 0, "backup_timestamp_seconds": 0}
    try:
        values = inspect(args.directory, args.ca, args.openssl, args.ssh_keygen, args.publisher_public_key)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        print("XRDP CRL monitoring failed: check signature, validity and recovery backup.")
    values["check_timestamp_seconds"] = time.time()
    output = args.metrics / ".xrdp-pki.prom.next"
    output.write_text("".join(f"xrdp_crl_{key} {value}\n" for key, value in values.items()))
    output.chmod(0o644)
    os.replace(output, args.metrics / "xrdp-pki.prom")
    return 0 if values["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
