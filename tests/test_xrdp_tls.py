"""Exercise XRDP renewal using disposable CAs, never production secrets."""
import importlib.util
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile
import tarfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "src/roles/nixos/files/etc/nixos/modules/xrdp-tls-renew.py"
spec = importlib.util.spec_from_file_location("xrdp_tls", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RenewalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / "tls"
        self.openssl = shutil.which("openssl")
        self.ca = self.root / "ca.pem"
        self.key = self.root / "ca-key.pem"
        self.make_ca(self.ca, self.key)
        self.state = self.root / "issuer"
        self.issuer = module.Issuer(self.state, self.ca, self.key, self.openssl)
        self.issuer.initialize()
        self.publications = []

    def run_ssl(self, *args):
        return subprocess.run([self.openssl, *map(str, args)], check=True,
                              capture_output=True).stdout

    def make_ca(self, cert, key, days=730):
        self.run_ssl("req", "-x509", "-newkey", "rsa:2048", "-nodes",
                     "-days", days, "-subj", "/CN=Disposable XRDP Test CA",
                     "-addext", "basicConstraints=critical,CA:TRUE",
                     "-addext", "keyUsage=critical,keyCertSign,cRLSign",
                     "-keyout", key, "-out", cert)

    def publish(self, crl, backup):
        self.publications.append(crl.read_bytes())
        with tarfile.open(backup) as archive:
            names = archive.getnames()
            self.assertIn("index", names)
            self.assertIn("crlnumber", names)
            self.assertFalse(any("key" in name or "ca.cnf" in name for name in names))

    def sign_backup(self, archive):
        identity = self.root / "backup-signer"
        ssh_keygen = shutil.which("ssh-keygen")
        if not identity.exists():
            subprocess.run([ssh_keygen, "-q", "-t", "ed25519", "-N", "", "-f", str(identity)],
                           check=True, capture_output=True)
        Path(str(archive) + ".sig").unlink(missing_ok=True)
        subprocess.run([ssh_keygen, "-Y", "sign", "-n", "xrdp-pki-state", "-f", str(identity), str(archive)],
                       check=True, capture_output=True)
        return ssh_keygen, Path(str(identity) + ".pub")

    def renew(self, publisher=None):
        return module.renew(self.target, self.ca, self.key, self.openssl, os.getgid(),
                            state=self.state, publisher=publisher or self.publish)

    def test_first_issue_permissions_names_and_idempotence(self):
        self.assertTrue(self.renew())
        current = self.target / "current"
        before = current.readlink()
        self.assertFalse(self.renew())
        self.assertEqual(before, current.readlink())
        self.assertEqual(0o640, (current / "key.pem").stat().st_mode & 0o777)
        self.assertEqual(0o750, current.stat().st_mode & 0o777)
        self.assertEqual(self.ca.read_bytes(), (current / "ca.pem").read_bytes())
        text = self.run_ssl("x509", "-in", current / "cert.pem", "-noout", "-text").decode()
        self.assertIn("CA:FALSE", text)
        self.assertIn("TLS Web Server Authentication", text)
        self.assertIn(module.CRL_URL, text)
        self.assertEqual(2, len(self.publications))
        self.assertNotEqual(self.publications[0], self.publications[1])
        self.assertIn("DNS:bullit", text)
        self.assertIn("IP Address:10.229.10.10", text)
        self.assertNotIn("CA-key", " ".join(p.name for p in current.iterdir()))

    def test_noop_repairs_parent_directory_access(self):
        self.renew()
        before = (self.target / "current").readlink()
        # Model systemd resetting StateDirectory before a no-op renewal.
        self.target.chmod(0o700)
        self.assertFalse(self.renew())
        self.assertEqual(before, (self.target / "current").readlink())
        self.assertEqual(0o750, self.target.stat().st_mode & 0o777)
        self.assertEqual(os.getgid(), self.target.stat().st_gid)

    def test_expiring_leaf_is_renewed_and_old_generations_are_bounded(self):
        self.renew()
        for _ in range(3):
            old = (self.target / "current").readlink()
            # Re-sign a one-day leaf with the existing leaf key, same valid SANs.
            current = self.target / "current"
            request = self.root / "leaf.csr"
            ext = self.root / "ext.cnf"
            ext.write_text("subjectAltName=DNS:bullit,DNS:bullit.net.scetrov.live,IP:10.229.10.10\n")
            self.run_ssl("req", "-new", "-key", current / "key.pem", "-subj", "/CN=bullit", "-out", request)
            self.run_ssl("x509", "-req", "-in", request, "-CA", self.ca,
                         "-CAkey", self.key, "-set_serial", "99", "-days", "1",
                         "-extfile", ext, "-out", current / "cert.pem")
            self.assertTrue(self.renew())
            self.assertNotEqual(old, (self.target / "current").readlink())
        self.assertEqual(2, len(list(self.target.glob("pair-*"))))

    def test_signing_failure_keeps_previous_pair(self):
        self.renew()
        before = (self.target / "current").readlink()
        leaf_key = (self.target / "current/key.pem").read_bytes()
        different = self.root / "different-key.pem"
        self.make_ca(self.root / "other-ca.pem", different)
        self.key.write_bytes(different.read_bytes())
        # A mismatched signing key must fail, never silently create a new CA.
        with self.assertRaises(subprocess.CalledProcessError):
            self.renew()
        self.assertEqual(before, (self.target / "current").readlink())
        self.assertEqual(leaf_key, (self.target / "current/key.pem").read_bytes())
        self.assertEqual(1, len(list(self.target.glob("pair-*"))))

    def test_near_expiry_ca_fails_before_replacing_current(self):
        self.renew()
        before = (self.target / "current").readlink()
        self.make_ca(self.ca, self.key, days=30)
        with self.assertRaises((subprocess.CalledProcessError, ValueError)):
            self.renew()
        self.assertEqual(before, (self.target / "current").readlink())

    def test_publication_failure_never_activates_a_new_pair(self):
        def unavailable(crl, backup):
            raise OSError("test publication unavailable")
        with self.assertRaises(OSError):
            self.renew(unavailable)
        self.assertFalse((self.target / "current").exists())
        self.assertEqual([], list(self.target.glob("pair-*")))
        # The issued public record survives even though its private key is gone.
        self.assertEqual(1, len(list((self.state / "newcerts").glob("*.pem"))))
        self.assertTrue(self.renew())

    def test_revocation_survives_restart_and_replaces_revoked_leaf(self):
        self.renew()
        old = (self.target / "current").readlink()
        certificate = self.root / "revoked.pem"
        certificate.write_bytes((self.target / "current/cert.pem").read_bytes())
        with self.issuer.locked():
            self.issuer.import_certificate(certificate, revoke=True)
        self.assertTrue(self.renew())
        self.assertNotEqual(old, (self.target / "current").readlink())
        result = subprocess.run([self.openssl, "verify", "-CAfile", str(self.ca),
                                 "-CRLfile", str(self.state / "crl.pem"), "-crl_check",
                                 str(certificate)], capture_output=True)
        self.assertNotEqual(0, result.returncode)
        self.assertIn(b"certificate revoked", result.stderr)

    def test_missing_state_and_partial_state_fail_closed(self):
        shutil.rmtree(self.state)
        with self.assertRaises(ValueError):
            self.renew()
        self.state.mkdir()
        (self.state / "index").write_text("")
        with self.assertRaises(ValueError):
            self.issuer.initialize()

    def test_initialization_is_idempotent_and_preserves_records(self):
        self.renew()
        before = (self.state / "index").read_bytes()
        self.assertFalse(self.issuer.initialize())
        self.assertEqual(before, (self.state / "index").read_bytes())

    def test_expiring_root_cannot_issue_first_leaf(self):
        shutil.rmtree(self.state)
        self.make_ca(self.ca, self.key, days=30)
        self.issuer.initialize()
        with self.assertRaises(subprocess.CalledProcessError):
            self.renew()
        self.assertFalse((self.target / "current").exists())

    def test_der_import_preserves_explicit_revocation(self):
        self.renew()
        certificate = self.target / "current/cert.pem"
        der = self.root / "legacy.cer"
        self.run_ssl("x509", "-in", certificate, "-outform", "DER", "-out", der)
        migrated = module.Issuer(self.root / "migrated", self.ca, self.key, self.openssl)
        self.assertTrue(migrated.initialize(imports=[certificate], revoked=[der]))
        self.assertEqual("R", migrated.status(migrated.serial(certificate)))

    def test_recovery_archive_restores_revocations_without_private_keys(self):
        self.renew()
        certificate = self.target / "current/cert.pem"
        with self.issuer.locked():
            self.issuer.import_certificate(certificate, revoke=True)
            self.issuer.crl()
            archive = self.issuer.backup()
        ssh_keygen, public_key = self.sign_backup(archive)
        restored = self.root / "restored"
        recovered = module.Issuer(restored, self.ca, self.key, self.openssl)
        module.restore(recovered, archive, ssh_keygen=ssh_keygen, public_key=public_key)
        with recovered.locked():
            self.assertEqual("R", recovered.status(recovered.serial(certificate)))
            recovered.crl()
        self.assertEqual(self.ca.read_bytes(), (self.target / "current/ca.pem").read_bytes())

    def test_publisher_pins_ssh_and_requires_exact_https_roundtrip(self):
        self.renew()
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = b"wrong CRL"
        with mock.patch.object(module.subprocess, "run") as command, \
                mock.patch.object(module.urllib.request, "build_opener") as opener:
            opener.return_value.open.return_value = response
            def signed(command_args, **kwargs):
                if "sign" in command_args:
                    Path(str(self.state / "state.tar.gz") + ".sig").write_bytes(b"test signature")
                return subprocess.CompletedProcess(command_args, 0)
            command.side_effect = signed
            with self.assertRaises(ValueError):
                module.publish(self.state / module.CRL_NAME, self.state / "state.tar.gz",
                               sftp="sftp", identity=self.root / "publisher",
                               known_hosts=self.root / "hosts", trust_bundle=self.ca)
            arguments = command.call_args.args[0]
            self.assertIn("-oStrictHostKeyChecking=yes", arguments)
            self.assertIn("-oIdentitiesOnly=yes", arguments)
            batch = command.call_args.kwargs["input"].decode()
            self.assertLess(batch.index("rename .state.next"), batch.index("rename .crl.next"))
            self.assertNotIn("rename -f ", batch)
            response.read.return_value = (self.state / module.CRL_NAME).read_bytes()
            module.publish(self.state / module.CRL_NAME, self.state / "state.tar.gz",
                           sftp="sftp", identity=self.root / "publisher",
                           known_hosts=self.root / "hosts", trust_bundle=self.ca)
            handlers = opener.call_args.args
            redirects = [h for h in handlers if isinstance(h, module.urllib.request.HTTPRedirectHandler)]
            with self.assertRaises(ValueError):
                redirects[0].redirect_request(None)

    def test_crl_monitor_detects_tampering_and_missing_backups(self):
        self.renew()
        monitor_spec = importlib.util.spec_from_file_location(
            "xrdp_monitor", SCRIPT.with_name("xrdp-crl-monitor.py"))
        monitor = importlib.util.module_from_spec(monitor_spec)
        monitor_spec.loader.exec_module(monitor)
        public = self.root / "published"
        public.mkdir()
        shutil.copyfile(self.state / module.CRL_NAME, public / module.CRL_NAME)
        with self.assertRaises(ValueError):
            monitor.inspect(public, self.ca, self.openssl, "ssh-keygen", self.root / "unused")
        archive = public / "state-0.tar.gz"
        shutil.copyfile(self.state / "state.tar.gz", archive)
        ssh_keygen, public_key = self.sign_backup(archive)
        self.assertEqual(1, monitor.inspect(public, self.ca, self.openssl, ssh_keygen, public_key)["valid"])
        other_ca = self.root / "untrusted-ca.pem"
        self.make_ca(other_ca, self.root / "untrusted-key.pem")
        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
            monitor.inspect(public, other_ca, self.openssl, ssh_keygen, public_key)
        (public / module.CRL_NAME).write_bytes(b"invalid CRL")
        with self.assertRaises(subprocess.CalledProcessError):
            monitor.inspect(public, self.ca, self.openssl, ssh_keygen, public_key)

    def test_tampered_recovery_archive_is_rejected(self):
        self.renew()
        archive = self.state / "state.tar.gz"
        ssh_keygen, public_key = self.sign_backup(archive)
        archive.write_bytes(archive.read_bytes() + b"tampering")
        recovered = module.Issuer(self.root / "recovered", self.ca, self.key, self.openssl)
        with self.assertRaises(subprocess.CalledProcessError):
            module.restore(recovered, archive, ssh_keygen=ssh_keygen, public_key=public_key)
        self.assertFalse(recovered.state.exists())

    def test_bad_key_pair_is_repaired(self):
        self.renew()
        (self.target / "current/key.pem").write_text("invalid key")
        self.assertTrue(self.renew())
        ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER).load_cert_chain(
            self.target / "current/cert.pem", self.target / "current/key.pem")


if __name__ == "__main__":
    unittest.main()
