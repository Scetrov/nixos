# Habiki live verification — 2026-10-18

## Approved maintenance cutover (task 3.3 complete)

Operator approved the maintenance window, targeted Ansible/Vault/NixOS activation
and the existing uncommitted-tree guard override. Two runs used:

```bash
./scripts/play.sh --limit habiki --tags nixos --skip-generated-refresh -- \
  -e nixos_miniflux_only=true -e nixos_force_deploy=true
```

1. Temporary repository override `postgresqlTLSOnly = false`: deployment exit 0,
   Habiki `ok=89 changed=17 unreachable=0 failed=0 skipped=16`.
2. Verified real clients, then removed the temporary override (default TLS-only).
   Enforcement deployment exit 0, Habiki `ok=89 changed=15 unreachable=0 failed=0 skipped=16`.

Channel updates, Frontier maintenance and blanket Podman restarts were skipped
through the existing maintenance guard. The full declarative host still activated;
this was not represented as a PostgreSQL-only NixOS switch. No image upgrade,
database reinitialization, explicit credential rotation or OpenTofu apply occurred.
The secrets role regenerated/delivered Miniflux's encrypted runtime URL from Vault.
The temporary mixed-mode override is absent from the final repository state.

## Real clients and transport

- PostgreSQL reports `ssl=on` and zero HBA errors. Final network admission is
  `hostnossl all all all reject` followed by TLS/SCRAM rules; local administration
  and local replication socket rules remain intact.
- Authentik server AND worker: inspected only non-secret host/mode/CA settings;
  opened fresh psycopg connections using each actual runtime's existing secret
  loader. Both use `postgres.net.scetrov.live`, `verify-full`, and the packaged
  `/etc/ssl/certs/ca-certificates.crt`; fresh sessions and application sessions
  use **TLS 1.3**. Plaintext retries with those real credentials were rejected by
  PostgreSQL on the private container network, without fallback.
- Miniflux: active systemd credential was parsed without printing it. Hostname,
  `verify-full` and explicit host CA bundle match the implementation. Actual
  Miniflux sessions use **TLS 1.3**.
- OpenTofu: exclusively `./scripts/tofu.sh -- plan -refresh=false`, before and
  after enforcement. Both exits 0 and report **No changes**; the verified pg
  backend initialized successfully. No state/apply mutation was requested.
- Direct PostgreSQL protocol/TLS checks to `habiki.net.scetrov.live:5433` verified
  trust/hostname and TLS 1.3. Wrong hostname and an untrusted CA store failed
  verification without fallback. Plaintext startup on the host port was rejected
  by PostgreSQL HBA (`no encryption`), not merely by a firewall.
- PostgreSQL container loopback plaintext rejected on **127.0.0.1 and ::1**.
- Restricted local socket queries remained available after enforcement.
- HTTP 200: native Miniflux health, Caddy-proxied feed health, Authentik readiness,
  and Miniflux OIDC discovery. This confirms health/discovery, not an interactive
  human OIDC login test.
- Preparation, PostgreSQL, Authentik server/worker, Miniflux, Caddy and Alloy all
  active after cutover and after the reload exercise.
- Container certificate directory/current generation: root:GID70, 0750; key:
  root:GID70, 0640. Container UID/GID maps remain identity mappings; host GID70 has
  no named group. No key contents or connection credentials were printed.

Initial cutover leaf certificate SHA256:
`a5c1338ceb73b5b485bcc2c2b6edee230c53227a4a99aeb3e20692eb046d09e8`.
Expiry: **2026-12-31 05:38:02 UTC**. This was the original certificate; the
subsequent genuine replacement is recorded below.

## Initial same-pair renewal handoff

An Ansible `ansible.builtin.systemd_service` reload of
`postgresql-tls-prepare.service` succeeded in the approved window. Actual
`ExecReload` exited 0 at **16:45:18 UTC**. Preparation republished the validated
pair and sent PostgreSQL HUP. PostgreSQL start time before AND after:
**2026-10-18 16:43:21.114611 UTC** — no database restart. A fresh verified
connection served the expected certificate; feed/identity Caddy HTTPS remained
HTTP 200. This tests handoff with the same certificate, **not replacement**.

Actual systemd dependencies inspected: preparation requires/comes after
`acme-scetrov.live.service`; PostgreSQL requires/comes after preparation. The
preparation unit has `ExecReload`, so ACME's try-reload-or-restart can reload it
rather than restart a required database dependency. No reboot had occurred at
this initial handoff-check stage.

## Genuine replacement without PostgreSQL restart (task 3.4 complete)

The operator approved `acceptance-plan.md`. The opt-in, Habiki-only
`src/postgresql-tls-acceptance.yml` ran once with the explicit renewal flag:
exit 0, `ok=24 changed=11 unreachable=0 failed=0 skipped=0 rescued=0 ignored=0`.
Only the existing renewal unit's runtime command was temporarily changed from
`--dynamic` to `--days 90`, with automatic retries disabled. Original credential
loading, sandbox, domain/account configuration and postrun hooks were preserved.
No credential/key material was copied into the playbook or Git.

- Previous serial: `05059DB677A342CAB5C5D7FCC4C488F34011`.
- Replacement serial: `062A5929F61EB50BE18489B1AE9109F074B9`.
- Replacement leaf SHA256:
  `d44ceda65da4df4d5c7f081a5138195a39c00a9c4b34eb518cae51134ccf2c76`.
- New expiry: **2027-01-16 16:12:57 UTC**.
- Fresh PostgreSQL and Caddy TLS connections both served the replacement leaf.
- PostgreSQL start time remained **2026-10-18 16:43:21.114611 UTC**; container ID
  remained `650157c7f756b0e4d7f1a3f74d047cafdf18d4ec5cfd1e2965efa6c6620b28a2`.
- One real, verified Authentik psycopg session in autocommit mode remained open
  throughout renewal. Backend PID **541** and PostgreSQL start time were identical
  before/after; its post-renewal query succeeded.
- The actual ACME postrun reloaded Caddy and PostgreSQL preparation; application
  health and TLS-only policy remained good.
- Mandatory cleanup passed: runtime script/directory/drop-in removed, original
  renewal executable restored, renewal unit idle, normal timer restored active.

This is actual issuance and served-replacement evidence, not the earlier
same-certificate reload exercise.

## Separately approved reboot and post-boot verification

The operator separately confirmed a recovery route and approved rebooting Habiki.
The first attempt stopped **before reboot**, with `changed=false`: Ansible's
reboot action searched only FHS directories and did not find `shutdown`. SSH
inspection confirmed `/run/current-system/sw/bin/shutdown` and all services still
active with unchanged PostgreSQL start time. Ansible's documented `search_paths`
option was researched; the operator approved correction/retry. The reboot play
now checks that executable and explicitly searches `/run/current-system/sw/bin`;
regression tests cover both controls.

`src/postgresql-tls-reboot.yml` then passed: exit 0,
`ok=8 changed=1 unreachable=0 failed=0 skipped=0 rescued=0 ignored=0`.

- Boot ID before: `25acde5a-70bb-4d0b-a6ed-b5fa4a181e6a`.
- Boot ID after: `bf68cacd-40b6-404a-b8bb-b6dfbab08a25`.
- Preparation completed at monotonic **11,416,786 microseconds**; PostgreSQL
  execution started at **21,740,000 microseconds** in the new boot.
- PostgreSQL start time after the intentional reboot:
  **2026-10-18 17:19:13.965789 UTC**.
- PostgreSQL and Caddy still serve the accepted replacement leaf; the root:GID70,
  0640 private-key permissions remain correct.
- Fresh actual Authentik server AND worker connections use `verify-full` and TLS
  1.3; their plaintext attempts are rejected on the private container network.
- Miniflux's active credential still has the verified endpoint and CA settings;
  actual native Miniflux sessions use TLS 1.3. No credential value was printed.
- Wrong hostname, untrusted CA store and host-port plaintext rejected again after
  boot. IPv4/IPv6 database loopback plaintext rejected; socket queries succeeded.
- Feed health, Authentik readiness, OIDC discovery and Caddy HTTPS passed; all
  scoped service units, including Alloy, are active.
- Post-boot `./scripts/tofu.sh -- plan -refresh=false` exited 0, **No changes**.
  No OpenTofu apply occurred. Protected state transport is verified across boot.

Task 3.4 acceptance is complete. The separate Garage transport prerequisite now
has evidence; the Garage proposal itself was not modified.

Reference for the corrected reboot lookup:
https://docs.ansible.com/ansible/latest/collections/ansible/builtin/reboot_module.html#parameter-search_paths

Protected local diagnostic directories (mode 0700, log files 0600; not in Git):
`/tmp/postgresql-tls-cutover-HrzQu7`, `/tmp/postgresql-tls-enforce-NDtapX`,
`/tmp/postgresql-tls-tofu-check-5bpdTn`, `/tmp/postgresql-tls-reload-WTQHiG`,
`/tmp/postgresql-tls-real-renewal-NEnLSl`, `/tmp/postgresql-tls-reboot-xcQomk`,
`/tmp/postgresql-tls-reboot-retry-NiRTO6`. These may contain operational metadata;
do not publish raw logs or backend caches.
