"""Credential-free certificate publication and shared-instance configuration checks."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import ssl
import socket
import subprocess
import threading
import tempfile
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "src/roles/nixos/files/etc/nixos/modules"
spec = importlib.util.spec_from_file_location("pg_tls", MODULES / "postgresql-tls-prepare.py")
pg_tls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pg_tls)


@unittest.skipUnless(shutil.which("openssl"), "openssl required for synthetic certificate tests")
class CertificateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "acme"
        self.source.mkdir()
        self.target = self.base / "postgresql"
        self.openssl = shutil.which("openssl")
        self.ca = self.base / "ca.pem"
        self.run_ssl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
                     "-subj", "/CN=Synthetic test CA", "-addext", "keyUsage=critical,keyCertSign,cRLSign",
                     "-keyout", str(self.base / "ca.key"),
                     "-out", str(self.ca))
        self.issue("postgres.net.scetrov.live", "habiki.net.scetrov.live")

    def run_ssl(self, *args):
        subprocess.run([self.openssl, *args], check=True, capture_output=True, timeout=15)

    def issue(self, *names, days=1):
        extensions = self.base / "extensions"
        extensions.write_text("subjectAltName=" + ",".join("DNS:" + n for n in names)
                              + "\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n")
        self.run_ssl("req", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=" + names[0],
                     "-keyout", str(self.source / "key.pem"), "-out", str(self.base / "request"))
        self.run_ssl("x509", "-req", "-in", str(self.base / "request"), "-CA", str(self.ca),
                     "-CAkey", str(self.base / "ca.key"), "-set_serial", "1", "-days", str(days),
                     "-extfile", str(extensions), "-out", str(self.source / "fullchain.pem"))

    def publish(self, ca=None):
        pg_tls.publish(self.source, self.target, ca or self.ca, self.openssl,
                       uid=os.getuid(), gid=os.getgid())

    def test_valid_pair_permissions_and_atomic_renewal(self):
        self.publish()
        original = (self.target / "current").resolve()
        self.assertEqual(original.parent, self.target)
        self.assertEqual((original / "key.pem").stat().st_mode & 0o777, 0o640)
        self.assertEqual(original.stat().st_mode & 0o777, 0o750)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o750)
        self.assertEqual((original / "key.pem").stat().st_gid, os.getgid())
        self.assertEqual(sorted(p.name for p in original.iterdir()), ["fullchain.pem", "key.pem"])
        self.issue("habiki.net.scetrov.live", "postgres.net.scetrov.live")
        self.publish()
        self.assertNotEqual((self.target / "current").resolve(), original)
        self.assertTrue(original.exists())  # Explicit recovery, not automatic rollback.

    def assert_rejected(self, ca=None):
        original = (self.target / "current").resolve()
        cert = (original / "fullchain.pem").read_bytes()
        with self.assertRaises((ssl.SSLError, subprocess.SubprocessError)):
            self.publish(ca)
        self.assertEqual((self.target / "current").resolve(), original)
        self.assertEqual((original / "fullchain.pem").read_bytes(), cert)
        self.assertFalse((self.target / ".next").exists())
        self.assertEqual(len(list(self.target.glob("pair-*"))), 1)

    def test_mismatched_key_leaves_working_pair_untouched(self):
        self.publish()
        shutil.copyfile(self.base / "ca.key", self.source / "key.pem")
        self.assert_rejected()

    def test_wrong_hostname_leaves_working_pair_untouched(self):
        self.publish()
        self.issue("wrong.invalid")
        self.assert_rejected()

    def test_wrong_ca_leaves_working_pair_untouched(self):
        self.publish()
        other = self.base / "other.pem"
        self.run_ssl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                     "-subj", "/CN=Untrusted CA", "-keyout", str(self.base / "other.key"),
                     "-out", str(other))
        self.assert_rejected(other)

    def test_expired_certificate_leaves_working_pair_untouched(self):
        self.publish()
        self.issue("habiki.net.scetrov.live", "postgres.net.scetrov.live", days=0)
        self.assert_rejected()

    def handshake(self, hostname, trust=True):
        # socketpair exercises real TLS without network access or listeners.
        server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server.load_cert_chain(self.source / "fullchain.pem", self.source / "key.pem")
        client = ssl.create_default_context(cafile=str(self.ca) if trust else None)
        left, right = socket.socketpair()
        left.settimeout(5)
        right.settimeout(5)
        def serve():
            try:
                with server.wrap_socket(left, server_side=True) as conn:
                    conn.recv(1)
            except ssl.SSLError:
                pass  # Expected client alert in negative tests.
            finally:
                left.close()
        thread = threading.Thread(target=serve)
        thread.start()
        try:
            with client.wrap_socket(right, server_hostname=hostname) as conn:
                conn.sendall(b"x")
                self.assertIsNotNone(conn.getpeercert())
        finally:
            right.close()
            thread.join(timeout=6)
            self.assertFalse(thread.is_alive())

    def test_verified_connection_and_invalid_client_verification(self):
        self.handshake("postgres.net.scetrov.live")
        self.handshake("habiki.net.scetrov.live")
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.handshake("wrong.invalid")
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.handshake("postgres.net.scetrov.live", trust=False)

    @unittest.skipUnless(os.environ.get("PG_TLS_CONTAINER_TEST") == "1",
                         "opt-in: requires approved host container runtime access")
    def test_populated_postgresql17_verified_tls_and_plaintext_rejection(self):
        # No published ports or external network; only synthetic inputs mounted.
        engine = os.environ.get("PG_TLS_TEST_ENGINE", "podman")
        name = "pg-tls-test-" + uuid.uuid4().hex[:12]
        image = "docker.io/library/postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24"
        env = dict(os.environ, POSTGRES_PASSWORD=uuid.uuid4().hex, PGPASSWORD="")
        env["PGPASSWORD"] = env["POSTGRES_PASSWORD"]
        inputs = self.source
        self.run_ssl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                     "-subj", "/CN=Wrong CA", "-keyout", str(self.base / "wrong-ca.key"),
                     "-out", str(inputs / "wrong-ca.pem"))
        inputs.chmod(0o755)
        shutil.copyfile(self.ca, inputs / "ca.pem")
        shutil.copyfile(MODULES / "postgresql-pg_hba.conf", inputs / "pg_hba.conf")
        conf = inputs / "server.conf"
        settings = "listen_addresses='*'\nhba_file='/config/pg_hba.conf'\n"
        conf.write_text(settings + "ssl=off\n")
        for file in inputs.iterdir():
            if file.name != "key.pem":
                file.chmod(0o644)

        def run(*args, check=True):
            result = subprocess.run([engine, *args], env=env, capture_output=True,
                                    text=True, timeout=120)
            if check and result.returncode:
                raise RuntimeError("Disposable PostgreSQL command failed; synthetic diagnostics suppressed")
            return result

        def psql(sql, connection=None, check=True):
            args = ["exec", "--env", "PGPASSWORD", name, "psql", "-XAt", "-v", "ON_ERROR_STOP=1"]
            args += ["-d", connection] if connection else ["-U", "authentik", "-d", "authentik"]
            return run(*args, "-c", sql, check=check)

        def ready():
            for _ in range(60):
                result = run("exec", name, "cat", "/proc/1/comm", check=False)
                if result.stdout.strip() == "postgres" and psql("SELECT 1", check=False).returncode == 0:
                    return
                time.sleep(1)
            raise RuntimeError("Disposable PostgreSQL readiness deadline exceeded")

        try:
            run("run", "--detach", "--pull=never", "--name", name, "--network=none",
                "--env", "POSTGRES_PASSWORD", "--env", "POSTGRES_USER=authentik",
                "--volume", name + "-data:/var/lib/postgresql/data",
                "--volume", name + "-tls:/run/postgresql-tls",
                "--volume", str(inputs) + ":/config:ro", image,
                "postgres", "-c", "config_file=/config/server.conf")
            ready()
            psql("CREATE TABLE tls_preserved(value integer); INSERT INTO tls_preserved VALUES (42)")
            run("exec", "--user", "0", name, "sh", "-c",
                "install -d -m 0750 -o 0 -g 70 /run/postgresql-tls/current && "
                "install -m 0640 -o 0 -g 70 /config/key.pem /run/postgresql-tls/current/key.pem && "
                "install -m 0644 -o 0 -g 70 /config/fullchain.pem /run/postgresql-tls/current/fullchain.pem")
            conf.write_text(settings + "ssl=on\nssl_cert_file='/run/postgresql-tls/current/fullchain.pem'\n"
                            "ssl_key_file='/run/postgresql-tls/current/key.pem'\n")
            run("restart", name)
            ready()
            connection = ("host=postgres.net.scetrov.live hostaddr=127.0.0.1 user=authentik "
                          "dbname=authentik sslmode=verify-full sslrootcert=/config/ca.pem")
            self.assertEqual(psql("SELECT value FROM tls_preserved", connection).stdout.strip(), "42")
            self.assertEqual(psql("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()", connection).stdout.strip(), "t")
            wrong_host = psql("SELECT 1", connection.replace("host=postgres.net.scetrov.live", "host=wrong.invalid"), check=False)
            self.assertNotEqual(wrong_host.returncode, 0)
            self.assertIn("certificate", wrong_host.stderr.lower())
            wrong_ca = psql("SELECT 1", connection.replace("sslrootcert=/config/ca.pem", "sslrootcert=/config/wrong-ca.pem"), check=False)
            self.assertNotEqual(wrong_ca.returncode, 0)
            self.assertIn("certificate", wrong_ca.stderr.lower())
            plaintext = psql("SELECT 1", connection.replace("sslmode=verify-full", "sslmode=disable"), check=False)
            self.assertNotEqual(plaintext.returncode, 0)
            self.assertIn("no encryption", plaintext.stderr.lower())
            self.assertEqual(psql("SELECT value FROM tls_preserved").stdout.strip(), "42")
        finally:
            run("rm", "--force", name, check=False)
            run("volume", "rm", name + "-data", name + "-tls", check=False)

    def test_malformed_certificate_leaves_working_pair_untouched(self):
        self.publish()
        (self.source / "fullchain.pem").write_text("not a certificate")
        self.assert_rejected()


class ConfigurationSourceTests(unittest.TestCase):
    def test_existing_cluster_admission_and_local_recovery(self):
        source = (MODULES / "postgresql-tls.nix").read_text()
        hba = (MODULES / "postgresql-pg_hba.conf").read_text()
        self.assertIn('default = true;', source)
        self.assertIn('local all all trust', hba)
        self.assertIn('local replication all trust', hba)
        self.assertIn('hostnossl all all all reject', source)
        self.assertIn('hostnossl all all all scram-sha-256', source)
        self.assertIn('hostssl all all all scram-sha-256', hba)
        self.assertIn('builtins.readFile ./postgresql-pg_hba.conf', source)
        self.assertIn('"hba_file=/etc/postgresql/pg_hba.conf"', source)
        self.assertNotIn('POSTGRES_HOST_AUTH_METHOD', source)
        self.assertIn('ExecReload = prepare;', source)
        self.assertIn('podman kill --signal HUP', source)
        self.assertNotIn('podman restart', source)
        self.assertNotIn(':/var/lib/acme', source)

    def test_production_consumers_require_hostname_and_chain_verification(self):
        authentik = (MODULES / "authentik.nix").read_text()
        self.assertIn('"AUTHENTIK_POSTGRESQL__HOST": "postgres.net.scetrov.live"', authentik)
        self.assertIn('"AUTHENTIK_POSTGRESQL__SSLMODE": "verify-full"', authentik)
        self.assertIn('"AUTHENTIK_POSTGRESQL__SSLROOTCERT": "/etc/ssl/certs/ca-certificates.crt"', authentik)
        for path in (ROOT / "scripts/tofu.sh", ROOT / "src/roles/secrets/tasks/miniflux.yml"):
            source = path.read_text()
            self.assertNotIn('sslmode=disable', source)
            self.assertIn('@habiki.net.scetrov.live:5433/', source)
            self.assertIn('sslmode=verify-full&sslrootcert=/etc/ssl/certs/ca-certificates.crt', source)
        self.assertIn('no_log: true', (ROOT / "src/roles/secrets/tasks/miniflux.yml").read_text())
        self.assertIn('postgresql-tls-prepare', (MODULES / "alloy.nix").read_text())


if __name__ == "__main__":
    unittest.main()
