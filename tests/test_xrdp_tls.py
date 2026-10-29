"""Exercise XRDP renewal using disposable CAs, never production secrets."""
import importlib.util
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile
import unittest


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

    def run_ssl(self, *args):
        return subprocess.run([self.openssl, *map(str, args)], check=True,
                              capture_output=True).stdout

    def make_ca(self, cert, key, days=730):
        self.run_ssl("req", "-x509", "-newkey", "rsa:2048", "-nodes",
                     "-days", days, "-subj", "/CN=Disposable XRDP Test CA",
                     "-addext", "basicConstraints=critical,CA:TRUE",
                     "-addext", "keyUsage=critical,keyCertSign,cRLSign",
                     "-keyout", key, "-out", cert)

    def renew(self):
        return module.renew(self.target, self.ca, self.key, self.openssl, os.getgid())

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
        self.assertIn("DNS:bullit", text)
        self.assertIn("IP Address:10.229.10.10", text)
        self.assertNotIn("CA-key", " ".join(p.name for p in current.iterdir()))

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
        self.make_ca(self.ca, self.root / "different-key.pem")
        # A new CA certificate with the old CA key must fail, never self-sign.
        with self.assertRaises(subprocess.CalledProcessError):
            self.renew()
        self.assertEqual(before, (self.target / "current").readlink())
        self.assertEqual(leaf_key, (self.target / "current/key.pem").read_bytes())
        self.assertEqual(1, len(list(self.target.glob("pair-*"))))

    def test_near_expiry_ca_fails_before_replacing_current(self):
        self.renew()
        before = (self.target / "current").readlink()
        self.make_ca(self.ca, self.key, days=30)
        with self.assertRaises(subprocess.CalledProcessError):
            self.renew()
        self.assertEqual(before, (self.target / "current").readlink())

    def test_bad_key_pair_is_repaired(self):
        self.renew()
        (self.target / "current/key.pem").write_text("invalid key")
        self.assertTrue(self.renew())
        ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER).load_cert_chain(
            self.target / "current/cert.pem", self.target / "current/key.pem")


if __name__ == "__main__":
    unittest.main()
