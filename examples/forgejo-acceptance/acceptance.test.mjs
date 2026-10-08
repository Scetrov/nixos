import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { test } from 'node:test';

const read = (path) => readFileSync(path, 'utf8').trim();

test('checkout provides source without persistent Git credentials', () => {
  assert.ok(existsSync('README.md'));
  const config = read('.git/config');
  assert.ok(!/extraheader/i.test(config), 'persisted Git authentication header');
  assert.ok(!/https?:\/\/[^\s/]+@/.test(config), 'credential-bearing Git URL');
});

test('runtime enforces ceilings and unprivileged execution', () => {
  assert.equal(read('/sys/fs/cgroup/memory.max'), '2147483648');
  assert.equal(read('/sys/fs/cgroup/cpu.max'), '200000 100000');
  const status = read('/proc/self/status');
  assert.match(status, /^CapEff:\s+0000000000000000$/m);
  assert.match(status, /^NoNewPrivs:\s+1$/m);
});

test('job has no host sockets, service state or deployment credentials', () => {
  for (const path of ['/var/run/docker.sock', '/run/podman/podman.sock',
    '/var/lib/forgejo-runner-control', '/var/lib/forgejo', '/root/secrets', '/run/agenix']) {
    assert.ok(!existsSync(path), `unexpected host path: ${path}`);
  }
  // Do not print environment values. A normal per-job Forgejo token is expected;
  // it is not the host runner registration token or an infrastructure credential.
  const forbidden = /^(TF_VAR_|AWS_SECRET_ACCESS_KEY$|ANSIBLE_VAULT_PASSWORD$|AUTHENTIK_TOKEN$|FORGEJO_RUNNER_TOKEN$|FORGEJO_OIDC_CLIENT_SECRET$)/i;
  assert.ok(!Object.keys(process.env).some((name) => forbidden.test(name)));
});
