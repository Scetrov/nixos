#!/usr/bin/env python3
"""Durable OpenSSL XRDP issuer; publish revocation data before activating TLS."""
from __future__ import annotations

import argparse
import contextlib
import datetime
import fcntl
import hashlib
import os
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import tarfile
import tempfile
import time
import urllib.request

HOSTNAMES = ("bullit", "bullit.net.scetrov.live")
IP_ADDRESS = "10.229.10.10"
CRL_NAME = "bullit-xrdp.crl"
CRL_URL = f"https://crl.net.scetrov.live/{CRL_NAME}"


def run(openssl: str, *args: str) -> bytes:
    return subprocess.run([openssl, *args], check=True, capture_output=True,
                          timeout=60).stdout


class Issuer:
    def __init__(self, state: Path, ca: Path, key: Path, openssl: str):
        self.state, self.ca, self.key, self.openssl = state, ca, key, openssl
        self.config = state / "ca.cnf"

    def command(self, *args: str) -> bytes:
        return run(self.openssl, *args)

    def fingerprint(self) -> str:
        return hashlib.sha256(self.command("x509", "-in", str(self.ca),
                                           "-outform", "DER")).hexdigest()

    def configure(self, directory: Path | None = None) -> None:
        directory = directory or self.state
        text = (
            "[ca]\ndefault_ca=issuer\n[issuer]\n"
            f"database={directory}/index\nnew_certs_dir={directory}/newcerts\n"
            f"serial={directory}/serial\ncrlnumber={directory}/crlnumber\n"
            f"certificate={self.ca}\nprivate_key={self.key}\n"
            "default_md=sha256\ndefault_days=365\ndefault_crl_days=7\n"
            "unique_subject=no\npolicy=policy\nx509_extensions=leaf\n"
            "crl_extensions=crl\n[policy]\ncommonName=supplied\n"
            "[leaf]\nbasicConstraints=critical,CA:FALSE\n"
            "keyUsage=critical,digitalSignature,keyEncipherment\n"
            "extendedKeyUsage=serverAuth\nsubjectKeyIdentifier=hash\n"
            "authorityKeyIdentifier=keyid,issuer\n"
            f"subjectAltName=DNS:{HOSTNAMES[0]},DNS:{HOSTNAMES[1]},IP:{IP_ADDRESS}\n"
            f"crlDistributionPoints=URI:{CRL_URL}\n"
            "[crl]\nauthorityKeyIdentifier=keyid:always\n"
        )
        self.config.write_text(text)
        self.config.chmod(0o600)

    def check(self) -> None:
        for name in ("index", "index.attr", "serial", "crlnumber", "ca-sha256", "newcerts"):
            if not (self.state / name).exists():
                raise ValueError("Issuer state missing; explicit recovery required")
        if (self.state / "ca-sha256").read_text().strip() != self.fingerprint():
            raise ValueError("Issuer CA changed; explicit migration required")
        self.state.chmod(0o700)
        records = self.records()
        if records and int((self.state / "serial").read_text().strip(), 16) <= max(records):
            raise ValueError("Issuer serial counter would reuse a certificate serial")

    def records(self) -> dict:
        records = {}
        for line in (self.state / "index").read_text().splitlines():
            fields = line.split("\t")
            if len(fields) != 6 or fields[0] not in ("V", "R", "E"):
                raise ValueError("Malformed issuer index")
            serial = int(fields[3], 16)
            if serial in records:
                raise ValueError("Duplicate certificate serial")
            records[serial] = fields[0]
        return records

    @contextlib.contextmanager
    def locked(self):
        # Never create missing state automatically during renewal.
        self.check()
        with (self.state / ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self.check()
            self.configure()
            yield

    def serial(self, certificate: Path) -> str:
        value = self.command("x509", "-in", str(certificate), "-noout", "-serial")
        number = int(value.decode().strip().split("=", 1)[1], 16)
        text = f"{number:X}"
        return ("0" if len(text) % 2 else "") + text

    def status(self, serial: str) -> str | None:
        return self.records().get(int(serial, 16))

    def import_certificate(self, certificate: Path, revoke: bool = False) -> None:
        # Normalize PEM/DER input and validate issuer before accepting a record.
        with tempfile.TemporaryDirectory(dir=self.state) as temporary:
            normalized = Path(temporary) / "certificate.pem"
            self.command("x509", "-in", str(certificate), "-out", str(normalized))
            self.command("verify", "-no_check_time", "-CAfile", str(self.ca), str(normalized))
            serial = self.serial(normalized)
            existing = self.state / "newcerts" / f"{serial}.pem"
            status = self.status(serial)
            if status is None:
                self.command("ca", "-batch", "-config", str(self.config), "-valid", str(normalized))
                shutil.copyfile(normalized, existing)
            elif self.command("x509", "-in", str(existing), "-outform", "DER") != self.command(
                    "x509", "-in", str(normalized), "-outform", "DER"):
                raise ValueError("Certificate serial collision")
            if revoke and status != "R":
                self.command("ca", "-batch", "-config", str(self.config), "-revoke",
                             str(normalized), "-crl_reason", "cessationOfOperation")

    def initialize(self, imports=(), revoked=()) -> bool:
        if (self.state / "ca-sha256").exists():
            self.check()
            return False
        if self.state.exists() and any(self.state.iterdir()):
            raise ValueError("Refusing to reset partial issuer state")
        self.state.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".xrdp-ca-init-", dir=self.state.parent) as temporary:
            stage = Path(temporary) / "state"
            stage.mkdir(mode=0o700)
            (stage / "newcerts").mkdir(mode=0o700)
            (stage / "index").write_text("")
            (stage / "index.attr").write_text("unique_subject = no\n")
            (stage / "serial").write_text(self.command("rand", "-hex", "16").decode().strip() + "\n")
            (stage / "crlnumber").write_text(f"{time.time_ns():X}\n")
            (stage / "ca-sha256").write_text(self.fingerprint() + "\n")
            staged = Issuer(stage, self.ca, self.key, self.openssl)
            staged.configure()
            for certificate in imports:
                staged.import_certificate(certificate)
            for certificate in revoked:
                staged.import_certificate(certificate, revoke=True)
            largest = max(staged.records(), default=0)
            if int((stage / "serial").read_text().strip(), 16) <= largest:
                counter = f"{largest + 1:X}"
                (stage / "serial").write_text(("0" if len(counter) % 2 else "") + counter + "\n")
            # Persist configuration with final paths before the atomic move.
            staged.configure(self.state)
            os.replace(stage, self.state)
        return True

    def crl(self) -> Path:
        pem, der = self.state / "crl.pem.next", self.state / CRL_NAME
        self.command("ca", "-batch", "-config", str(self.config), "-gencrl", "-out", str(pem))
        self.command("crl", "-in", str(pem), "-verify", "-CAfile", str(self.ca), "-noout")
        self.command("crl", "-in", str(pem), "-outform", "DER", "-out", str(der))
        os.replace(pem, self.state / "crl.pem")
        der.chmod(0o644)
        return der

    def backup(self) -> Path:
        # Whitelist public CA records only: never include leaf/CA/SSH keys.
        path = self.state / "state.tar.gz"
        with tarfile.open(path, "w:gz") as archive:
            for name in ("index", "index.attr", "serial", "crlnumber", "ca-sha256", "newcerts", CRL_NAME):
                source = self.state / name
                if source.is_symlink() or (source.is_dir() and any(p.is_symlink() for p in source.rglob("*"))):
                    raise ValueError("Unexpected symlink in issuer records")
                archive.add(source, arcname=name)
        path.chmod(0o640)
        return path


def verify_backup(archive: Path, ssh_keygen: str, public_key: Path) -> None:
    if archive.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Recovery archive exceeds compressed size limit")
    with tempfile.TemporaryDirectory() as temporary:
        allowed = Path(temporary) / "allowed_signers"
        allowed.write_text("xrdp-crl-publisher " + public_key.read_text().strip() + "\n")
        subprocess.run([ssh_keygen, "-Y", "verify", "-f", str(allowed),
                        "-I", "xrdp-crl-publisher", "-n", "xrdp-pki-state",
                        "-s", str(archive) + ".sig"], input=archive.read_bytes(),
                       check=True, capture_output=True, timeout=30)


def restore(issuer: Issuer, archive: Path, *, ssh_keygen: str, public_key: Path) -> None:
    """Explicit, bounded recovery; never overwrite a nonempty issuer database."""
    if issuer.state.exists() and any(issuer.state.iterdir()):
        raise ValueError("Restore requires an absent or empty destination")
    verify_backup(archive, ssh_keygen, public_key)
    with tempfile.TemporaryDirectory(prefix=".xrdp-restore-", dir=issuer.state.parent) as temporary:
        stage = Path(temporary) / "state"
        stage.mkdir(mode=0o700)
        with tarfile.open(archive) as source:
            members = source.getmembers()
            allowed = {"index", "index.attr", "serial", "crlnumber", "ca-sha256", "newcerts", CRL_NAME}
            if len(members) > 20000 or sum(m.size for m in members) > 64 * 1024 * 1024:
                raise ValueError("Recovery archive exceeds limits")
            for member in members:
                if member.name not in allowed and not re.fullmatch(r"newcerts/[0-9A-Fa-f]+\.pem", member.name):
                    raise ValueError("Unexpected recovery archive member")
                if not member.isfile() and not (member.isdir() and member.name == "newcerts"):
                    raise ValueError("Recovery archive contains links or special files")
            source.extractall(stage, filter="data")
        recovered = Issuer(stage, issuer.ca, issuer.key, issuer.openssl)
        recovered.check()
        data = recovered.command("crl", "-inform", "DER", "-in", str(stage / CRL_NAME),
                                 "-verify", "-CAfile", str(issuer.ca), "-noout", "-text")
        signed_revocations = {int(s, 16) for s in re.findall(rb"Serial Number:\s*([0-9A-Fa-f]+)", data)}
        indexed_revocations = {s for s, status in recovered.records().items() if status == "R"}
        if signed_revocations != indexed_revocations:
            raise ValueError("Recovery revocations disagree with the signed CRL")
        for certificate in (stage / "newcerts").glob("*.pem"):
            recovered.command("verify", "-no_check_time", "-CAfile", str(issuer.ca), str(certificate))
        recovered.configure(issuer.state)
        os.replace(stage, issuer.state)


def publish(crl: Path, backup: Path, *, sftp: str, identity: Path,
            known_hosts: Path, trust_bundle: Path) -> None:
    slot = datetime.datetime.now(datetime.timezone.utc).weekday()
    signature = Path(str(backup) + ".sig")
    signature.unlink(missing_ok=True)
    subprocess.run([str(Path(sftp).with_name("ssh-keygen")), "-Y", "sign",
                    "-n", "xrdp-pki-state", "-f", str(identity), str(backup)],
                   check=True, capture_output=True, timeout=30)
    signature.chmod(0o640)
    # Upload backup before publishing the CRL. Seven fixed backup slots bound
    # storage without granting shell execution or relying on remote cron jobs.
    batch = (f'put -p "{backup}" .state.next\n'
             f'put -p "{signature}" .signature.next\n'
             f'rename .state.next state-{slot}.tar.gz\n'
             f'rename .signature.next state-{slot}.tar.gz.sig\n'
             f'put -p "{crl}" .crl.next\nrename .crl.next {CRL_NAME}\n')
    subprocess.run(
        [sftp, "-q", "-b", "-", "-i", str(identity), "-oBatchMode=yes",
         "-oIdentitiesOnly=yes", "-oStrictHostKeyChecking=yes", "-oConnectTimeout=10",
         f"-oUserKnownHostsFile={known_hosts}", "-oGlobalKnownHostsFile=/dev/null",
         "xrdp-crl-publisher@10.229.10.2"], input=batch.encode(),
        check=True, capture_output=True, timeout=90)

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise ValueError("CRL endpoint must not redirect")

    context = ssl.create_default_context(cafile=str(trust_bundle))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                                        urllib.request.HTTPSHandler(context=context))
    request = urllib.request.Request(CRL_URL, headers={"Cache-Control": "no-cache"})
    with opener.open(request, timeout=20) as response:
        data = response.read(1024 * 1024 + 1)
        if response.status != 200 or data != crl.read_bytes():
            raise ValueError("Published CRL did not round-trip over trusted HTTPS")


def renew(target: Path, ca: Path, ca_key: Path, openssl: str, gid: int,
          *, state: Path, publisher, renew_before: int = 30 * 86400) -> bool:
    issuer = Issuer(state, ca, ca_key, openssl)
    target.mkdir(mode=0o750, parents=True, exist_ok=True)
    os.chown(target, os.getuid(), gid)
    target.chmod(0o750)

    def validate(pair: Path) -> None:
        ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER).load_cert_chain(pair / "cert.pem", pair / "key.pem")
        for option, name in [("-verify_hostname", n) for n in HOSTNAMES] + [("-verify_ip", IP_ADDRESS)]:
            issuer.command("verify", "-purpose", "sslserver", "-CAfile", str(ca),
                           "-CRLfile", str(state / "crl.pem"), "-crl_check", option,
                           name, str(pair / "cert.pem"))
        issuer.command("x509", "-in", str(pair / "cert.pem"), "-noout", "-checkend", str(renew_before))
        if CRL_URL.encode() not in issuer.command("x509", "-in", str(pair / "cert.pem"), "-noout", "-text"):
            raise ValueError("Leaf needs production HTTPS CDP")
        if (pair / "ca.pem").read_bytes() != ca.read_bytes():
            raise ValueError("Leaf trust anchor changed")

    with issuer.locked():
        issuer.command("x509", "-in", str(ca), "-noout", "-checkend", str(366 * 86400))
        crl = issuer.crl()
        current = target / "current"
        try:
            validate(current)
            serial = issuer.serial(current / "cert.pem")
            if issuer.status(serial) != "V":
                raise ValueError("Current leaf missing from durable issuance records")
            changed = False
        except (OSError, ValueError, ssl.SSLError, subprocess.SubprocessError):
            changed = True
        stage = Path(tempfile.mkdtemp(prefix="pair-", dir=target)) if changed else None
        activated = False
        link = target / ".next"
        try:
            if stage:
                issuer.command("req", "-new", "-newkey", "rsa:3072", "-nodes", "-sha256",
                               "-subj", f"/CN={HOSTNAMES[1]}", "-keyout", str(stage / "key.pem"),
                               "-out", str(stage / "request.pem"))
                issuer.command("ca", "-batch", "-notext", "-config", str(issuer.config),
                               "-in", str(stage / "request.pem"), "-out", str(stage / "cert.pem"))
                shutil.copyfile(ca, stage / "ca.pem")
                validate(stage)
                (stage / "request.pem").unlink()
            # No early return: refresh revocation and remote recovery records
            # even when the leaf itself does not need to change.
            publisher(crl, issuer.backup())
            if stage:
                for name, mode in (("key.pem", 0o640), ("cert.pem", 0o644), ("ca.pem", 0o644)):
                    os.chown(stage / name, os.getuid(), gid)
                    (stage / name).chmod(mode)
                os.chown(stage, os.getuid(), gid)
                stage.chmod(0o750)
                link.unlink(missing_ok=True)
                link.symlink_to(stage.name, target_is_directory=True)
                os.replace(link, current)
                activated = True
                generations = sorted(target.glob("pair-*"), key=lambda p: p.stat().st_mtime, reverse=True)
                previous = next((p for p in generations if p != stage), None)
                for old in generations:
                    if old not in (stage, previous):
                        shutil.rmtree(old)
            return changed
        finally:
            link.unlink(missing_ok=True)
            if stage and not activated:
                shutil.rmtree(stage)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("init", "renew", "revoke", "restore"))
    for name in ("state", "ca", "ca-key"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--openssl", required=True)
    parser.add_argument("--import-cert", type=Path, action="append", default=[])
    parser.add_argument("--revoke-cert", type=Path, action="append", default=[])
    parser.add_argument("--target", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--ssh-keygen")
    parser.add_argument("--publisher-public-key", type=Path)
    parser.add_argument("--group", default="xrdp")
    parser.add_argument("--sftp")
    parser.add_argument("--identity", type=Path)
    parser.add_argument("--known-hosts", type=Path)
    parser.add_argument("--trust-bundle", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        issuer = Issuer(args.state, args.ca, args.ca_key, args.openssl)
        if args.action == "init":
            issuer.initialize(args.import_cert, args.revoke_cert)
            print("Issuer initialized or already present; no trust anchor changed.")
        elif args.action == "restore":
            if not all((args.archive, args.ssh_keygen, args.publisher_public_key)):
                raise ValueError("Explicit archive and verification key required")
            restore(issuer, args.archive, ssh_keygen=args.ssh_keygen, public_key=args.publisher_public_key)
            print("Issuer records restored; review latest publication before renewal.")
        elif args.action == "revoke":
            if not args.revoke_cert:
                raise ValueError("Explicit certificate required")
            with issuer.locked():
                for certificate in args.revoke_cert:
                    issuer.import_certificate(certificate, revoke=True)
            print("Revocation recorded; run renewal to publish immediately.")
        else:
            import grp
            if not all((args.target, args.sftp, args.identity, args.known_hosts, args.trust_bundle)):
                raise ValueError("Publication settings are required")
            def publisher(crl, backup):
                publish(crl, backup, sftp=args.sftp, identity=args.identity,
                        known_hosts=args.known_hosts, trust_bundle=args.trust_bundle)
            changed = renew(args.target, args.ca, args.ca_key, args.openssl,
                            grp.getgrnam(args.group).gr_gid, state=args.state, publisher=publisher)
            print("renewed" if changed else "CRL and recovery backup refreshed; leaf unchanged.")
    except subprocess.CalledProcessError as error:
        print(f"XRDP PKI subprocess {Path(error.cmd[0]).name} failed (exit {error.returncode}); no self-signed fallback.")
        return 1
    except (OSError, ValueError, ssl.SSLError, subprocess.SubprocessError, tarfile.TarError):
        print("XRDP PKI operation failed; inspect issuer state, publication and listener. No self-signed fallback.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
