"""Opt-in real rootless job DNS/TLS fixture against non-sensitive HTTPS paths.

Set FORGEJO_JOB_TEST_IMAGE to a digest-pinned Alpine network fixture image.
This validates transport, not the undeployed Forgejo application/OIDC/artifacts.
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / 'src/roles/nixos/files/etc/nixos/modules/forgejo-runner-config.json'


@unittest.skipUnless(os.environ.get('FORGEJO_JOB_TEST_IMAGE'), 'Set FORGEJO_JOB_TEST_IMAGE for actual rootless DNS/TLS probe')
class JobConnectivityTests(unittest.TestCase):
    def test_private_hostname_and_trusted_tls(self):
        image = os.environ['FORGEJO_JOB_TEST_IMAGE']
        self.assertRegex(image, r'^[a-z0-9.-]+/[a-z0-9_./-]+@sha256:[0-9a-f]{64}$')
        settings = json.loads(TEMPLATE.read_text())
        self.assertFalse(settings['runner']['insecure'])
        env = os.environ.copy()
        env['DBUS_SESSION_BUS_ADDRESS'] = 'unix:path=' + env['XDG_RUNTIME_DIR'] + '/bus'
        with tempfile.TemporaryDirectory(prefix='forgejo-connectivity-') as temporary:
            base = Path(temporary)
            runtime = ['podman', '--cgroup-manager=systemd', '--root', str(base / 'storage'), '--runroot', str(base / 'run')]
            def command(args):
                result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=120)
                self.assertEqual(result.returncode, 0, 'Rootless DNS/TLS fixture failed: ' + result.stderr[-1500:])
                return result.stdout
            try:
                command([*runtime, 'pull', image])
                output = command([*runtime, 'run', '--rm', *shlex.split(settings['container']['options']), image, 'sh', '-ec', '''
                    test "$(getent hosts source.net.scetrov.live | awk '{print $1}')" = 10.229.10.2
                    nslookup example.com 10.229.53.1 >/dev/null
                    nslookup example.com 10.229.53.2 >/dev/null
                    # Public wildcard certificate; no insecure TLS flags or CA bind mounts.
                    wget -q -O /dev/null https://source.net.scetrov.live/
                    wget -q -O /dev/null https://example.com/
                    # The IP is not a valid certificate hostname: trust checks must reject it.
                    if wget -q -O /dev/null https://10.229.10.2/ 2>/dev/null; then exit 1; fi
                    echo JOB_DNS_TLS_OK
                '''])
                self.assertIn('JOB_DNS_TLS_OK', output)
            finally:
                # Explicit isolated paths only, even on a failed fixture.
                subprocess.run([*runtime, 'system', 'reset', '--force'], env=env, capture_output=True, timeout=30)
