"""Opt-in egress packet fixture, never modifies the host network/firewall.

FORGEJO_EGRESS_TEST=1 python3 -m unittest scripts.tests.test_forgejo_runner_egress -v
Requires sudo -n, unshare, ip, iptables/ip6tables and nft (e.g. nix-shell).
"""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[2]


def probe(engine, manifest, uid, gid):
    # This function runs as root ONLY inside sudo unshare --net. Refuse the host
    # namespace even if somebody accidentally invokes the helper directly.
    if os.readlink('/proc/self/ns/net') == os.readlink('/proc/1/ns/net'):
        raise RuntimeError('Refusing host network namespace')
    def run(args, **kwargs):
        return subprocess.run(args, check=True, capture_output=True, text=True, **kwargs)
    run(['ip', 'link', 'set', 'lo', 'up'])
    addresses = ['10.229.10.2', '10.229.10.99', '10.229.53.1', '10.229.53.2',
                 '100.64.0.2', '169.254.1.2', '203.0.113.2', 'fd00::2', '2001:db8::2']
    for address in addresses:
        run(['ip', 'addr', 'add', address + ('/128' if ':' in address else '/32'), 'dev', 'lo'])
    rules = json.loads(Path(manifest).read_text())
    if engine == 'iptables':
        for tool in ('iptables', 'ip6tables'):
            run([tool, '-N', 'nixos-fw'])
            run([tool, '-N', 'nixos-fw-accept'])
        script = rules['egressStart'].replace('--uid-owner forgejo-runner', '--uid-owner ' + uid)
        # Repeat convergence must not duplicate owner jumps.
        run(['bash', '-eu', '-c', script])
        run(['bash', '-eu', '-c', rules['egressStop'].replace('--uid-owner forgejo-runner', '--uid-owner ' + uid)])
        run(['bash', '-eu', '-c', script])
    else:
        content = rules['egressNft'].replace('"forgejo-runner"', uid)
        run(['nft', '-f', '-'], input='table inet forgejo_job_fixture {\n' + content + '\n}')
    cases = [
        ('10.229.10.2', 443, True), ('10.229.10.2', 5432, False),
        ('10.229.10.99', 443, False), ('100.64.0.2', 443, False),
        ('169.254.1.2', 443, False), ('127.0.0.1', 80, False),
        ('203.0.113.2', 443, True), ('203.0.113.2', 80, True),
        ('203.0.113.2', 5432, False), ('fd00::2', 443, False),
        ('::1', 443, False), ('2001:db8::2', 443, True),
        ('10.229.53.1', 53, True), ('10.229.53.2', 53, True),
    ]
    listeners = []
    try:
        for address, port, expected in cases:
            family = socket.AF_INET6 if ':' in address else socket.AF_INET
            server = socket.socket(family)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if family == socket.AF_INET6:
                server.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            server.bind((address, port)); server.listen(10)
            listeners.append(server)
            client = 'import socket,sys; s=socket.socket(' + str(int(family)) + '); s.settimeout(1); sys.exit(0 if s.connect_ex((' + repr(address) + ',' + str(port) + ')) == 0 else 1)'
            # Root/control traffic must remain unaffected.
            run([sys.executable, '-c', client])
            result = subprocess.run(['setpriv', '--reuid=' + uid, '--regid=' + gid, '--clear-groups', sys.executable, '-c', client], capture_output=True)
            if (result.returncode == 0) != expected:
                raise AssertionError(f'{engine}: unexpected TCP admission {address}:{port}')
        for address in ('10.229.53.1', '10.229.53.2', '10.229.10.99'):
            server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            server.bind((address, 53)); server.settimeout(3)
            listeners.append(server)
            def respond(server=server):
                try:
                    data, peer = server.recvfrom(1024); server.sendto(data, peer)
                except (OSError, TimeoutError):
                    pass
            thread = threading.Thread(target=respond, daemon=True); thread.start()
            client = 'import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.settimeout(1); s.connect((' + repr(address) + ',53)); s.send(b"fixture"); assert s.recv(1024)==b"fixture"'
            result = subprocess.run(['setpriv', '--reuid=' + uid, '--regid=' + gid, '--clear-groups', sys.executable, '-c', client], capture_output=True)
            if (result.returncode == 0) != (address != '10.229.10.99'):
                raise AssertionError(f'{engine}: unexpected UDP DNS admission {address}')
        if engine == 'iptables':
            run(['bash', '-eu', '-c', rules['egressStop'].replace('--uid-owner forgejo-runner', '--uid-owner ' + uid)])
        else:
            run(['nft', 'delete', 'table', 'inet', 'forgejo_job_fixture'])
        run(['setpriv', '--reuid=' + uid, '--regid=' + gid, '--clear-groups', sys.executable, '-c', 'import socket; socket.create_connection(("10.229.10.2",5432),1).close()'])
    finally:
        for server in listeners:
            server.close()
    print(engine + ': TCP/UDP, IPv4/IPv6, unrelated-user and removal checks passed')


@unittest.skipUnless(os.environ.get('FORGEJO_EGRESS_TEST') == '1', 'Set FORGEJO_EGRESS_TEST=1 for isolated privileged packet tests')
class EgressTests(unittest.TestCase):
    def test_both_firewall_backends(self):
        self.assertNotEqual(os.getuid(), 0, 'Run the test as the unprivileged fixture user')
        for name in ('sudo', 'unshare', 'ip', 'iptables', 'ip6tables', 'nft', 'setpriv'):
            self.assertTrue(shutil.which(name), name + ' required')
        tool_path = ':'.join(sorted({str(Path(shutil.which(name)).resolve().parent)
                                     for name in ('unshare', 'ip', 'iptables', 'ip6tables', 'nft', 'setpriv', 'bash')}))
        evaluation = subprocess.run(['nix-instantiate', '--eval', '--strict', '--json', '--expr',
                                     'import ./src/roles/nixos/tests/forgejo-eval.nix {}'], cwd=ROOT, capture_output=True, text=True, check=True)
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / 'rules.json'
            manifest.write_text(evaluation.stdout)
            for backend in ('iptables', 'nft'):
                result = subprocess.run(['sudo', '-n', 'env', 'PATH=' + tool_path, 'unshare', '--net', sys.executable,
                                         str(Path(__file__).resolve()), '--probe', backend,
                                         str(manifest), str(os.getuid()), str(os.getgid())],
                                        capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-3000:])


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--probe':
        probe(*sys.argv[2:])
    else:
        unittest.main()
