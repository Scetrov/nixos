# Shared PostgreSQL TLS (Habiki)

Scope: only `authentik-postgresql`; preserve its PG17 image, data, databases,
roles, credentials and ports. Implementation is not evidence of live cutover.
See the change's `compatibility.md` for the inspected runtime inventory.

## Endpoints and trust

| Consumer | Endpoint | Verification |
| --- | --- | --- |
| Authentik server/worker | `postgres.net.scetrov.live:5432` | `AUTHENTIK_POSTGRESQL__SSLMODE=verify-full`, `AUTHENTIK_POSTGRESQL__SSLROOTCERT=/etc/ssl/certs/ca-certificates.crt` |
| Miniflux | `habiki.net.scetrov.live:5433/miniflux` | URL `sslmode=verify-full&sslrootcert=/etc/ssl/certs/ca-certificates.crt` |
| OpenTofu | `habiki.net.scetrov.live:5433/terraform_state` | Same verification; exclusively through `scripts/tofu.sh` |

`habiki.net.scetrov.live` already resolves through `local-networking.nix`.
`postgres.net.scetrov.live` is **Podman-network-only** DNS, not a host alias:
containers connect directly to the existing database, never through port 5433.
There is no new host port or proxy. Do not add that private alias to host DNS.
The ACME wildcard covers both names. Trust the public CA bundle, not a copied
server leaf. Socket-based maintenance needs no network TLS changes.

## Planned maintenance cutover

Agree a maintenance window and stop if any prerequisite fails. NixOS activation
can affect other Habiki services: review its plan before running. The command
below reuses the existing `nixos_miniflux_only` maintenance guard to skip channel
updates, Frontier maintenance, Garage provisioning and blanket Podman restarts;
it still activates the complete declarative host. Do not deploy to other hosts
or use the separate database-upgrade play.

The normal clean/pushed-tree deployment guard remains in force. If validating
this staged, not-yet-archived change, obtain explicit operator approval before
adding `-e nixos_force_deploy=true` to the trailing Ansible arguments; do not
silently bypass the guard, commit prematurely or archive incomplete live checks.

1. Finish local regression tests, quality gates and syntax/configuration checks.
   Confirm the current certificate's validity, existing secrets, actual container
   UID/GID **70:70** and identity mappings. Recheck the inventory for new clients.
   Ensure the existing encrypted generated OIDC outputs are current; no identity
   provisioning or credential rotation is part of this migration.
2. Temporarily set `scetrov.services.authentik.postgresqlTLSOnly = false;` in the
   repository's `src/roles/nixos/files/device-configuration/habiki.nix`. This is
   mixed-mode **only for this window**, not a committed steady-state setting.
   Deploy using existing secret rendering and NixOS automation:

   ```bash
   ./scripts/play.sh --limit habiki --tags nixos --skip-generated-refresh -- -e nixos_miniflux_only=true
   ```

   This one-time bootstrap flag avoids calling the newly TLS-only OpenTofu
   wrapper before PostgreSQL supports TLS. It does not bypass secret encryption:
   the secrets role still regenerates Miniflux's URL from Vault into agenix.
   Do not run the `miniflux` tag to bootstrap: it invokes OpenTofu first.
3. Confirm preparation succeeded, PostgreSQL has `ssl=on`, and HBA has no errors.
   Verify Authentik server AND worker health, OIDC login and Miniflux feed/API
   access. Check actual connections with the read-only socket command below.
   Independently check each configured client uses `verify-full` and the correct
   CA (the server's `pg_stat_ssl` cannot prove client-side verification).
4. From the normal operator environment run `./scripts/tofu.sh -- plan -refresh=false`
   to verify protected backend access without applying changes. Do not print
   `PG_CONN_STR`, environment files, Vault contents or backend caches. The wrapper
   initializes the backend and may refresh local provider caches; review its plan
   output for sensitive resource data before saving it.
5. Test fresh TCP connections with synthetic/test credentials: valid hostname/CA
   succeeds; wrong hostname or untrusted CA fails without fallback. Use a test
   credential through an approved protected file/environment, never argv. Do not
   change production client settings to bypass verification.
6. Restore `postgresqlTLSOnly = true` (or remove the temporary false override).
   Deploy the same targeted command, now safely using normal refresh if desired.
   Confirm plaintext TCP fails on IPv4/IPv6 loopback, the container network and
   host port, and verified real clients still work. Confirm socket administration.
   A failed acceptance check leaves this change incomplete; no automatic rollback
   may reopen plaintext.

Read-only administration, run on Habiki via the trusted `ssh scetrov@habiki` alias:

```bash
sudo podman exec authentik-postgresql psql -X --no-password -U authentik -d postgres \
  -c 'SHOW ssl;' \
  -c 'SELECT type,database,user_name,address,auth_method,error FROM pg_hba_file_rules ORDER BY rule_number;' \
  -c 'SELECT a.usename,a.datname,a.application_name,a.client_addr,s.ssl,s.version FROM pg_stat_activity a JOIN pg_stat_ssl s USING(pid) WHERE a.client_addr IS NOT NULL;'
```

## Local validation

Run the focused Python tests with installed OpenSSL on PATH and an installed
PyYAML-enabled Python for the existing Miniflux tests. Apply the Nix test function
with `nix-instantiate --eval --strict --expr 'import ./tests/postgresql-tls-eval.nix {}'`
using an approved read-only nixpkgs snapshot when required by local isolation.

The opt-in real PostgreSQL regression test needs separately approved host runtime
access. It uses the existing pinned PG17 image (`--pull=never`), `--network=none`,
no published ports, synthetic inputs and uniquely named disposable volumes:

```bash
PG_TLS_CONTAINER_TEST=1 python3 -m unittest \
  scripts.tests.test_postgresql_tls.CertificateTests.test_populated_postgresql17_verified_tls_and_plaintext_rejection
```

The test seeds a plaintext-era cluster, enables TLS on that same cluster,
validates root-owned/GID-70 key readability, verifies a fresh connection,
rejects wrong hostname/CA and plaintext, and preserves socket access and data.
It never connects to Habiki. Run the repository's full pre-commit gate as well.

## Renewal and startup checks

Only `/var/lib/authentik/postgresql-tls` is mounted into PostgreSQL, read-only.
Each protected pair has a root-owned, GID-70 directory (0750), key (0640) and
public chain (0644). ACME accounts and Cloudflare credentials remain outside.
The helper checks key matching, chain trust, time validity and both hostnames
before atomically changing `current`. Invalid replacements leave it untouched.
Previous protected generations remain for deliberate recovery; prune obsolete
ones only through reviewed automation after successful renewal acceptance.

Preparation requires/comes after `acme-scetrov.live.service` and precedes the
container. ACME appends `postgresql-tls-prepare.service` to its reload consumers;
`ExecReload` republishes and sends HUP, without restarting PostgreSQL or replacing
Caddy's hooks. Check the journal/Alloy stream (`service=authentik`) for failures.

In the agreed window, record PostgreSQL start time/PID and a fresh connection's
served certificate fingerprint/serial. Exercise existing ACME renewal automation
(`acme-order-renew-scetrov.live.service`); a no-op renewal is NOT replacement
proof. When a replacement is issued, wait for the preparation reload to finish,
verify a fresh PostgreSQL connection serves the new certificate, start time/PID
is unchanged, existing sessions survive and Caddy HTTPS still works. Do not force
issuance repeatedly or risk CA rate limits. A preparation reload alone checks
handoff but cannot prove certificate replacement.

For a **separately approved, one-off real replacement exercise**, use the opt-in
`src/postgresql-tls-acceptance.yml` play with `postgresql_tls_acceptance_renew=true`.
It is version-bound to the reviewed existing renewal script, pauses/restores only
that timer, makes one runtime-only days-threshold override, preserves the real
postrun/credential sandbox, verifies replacement without PostgreSQL restart and
cleans up in `always`. Never include it in normal deployment or repeat it to
work around a failure/CA rate limit. Hold a verified authenticated session across
the exercise and verify it survives as well.

The separate `src/postgresql-tls-reboot.yml` play requires explicit
`postgresql_tls_acceptance_reboot=true`, `postgresql_tls_recovery_confirmed=true`
and the accepted public `postgresql_tls_expected_fingerprint`. Confirm recovery
access first. It checks NixOS's shutdown executable and supplies Ansible's explicit
`search_paths` (the reboot action ignores remote PATH), then verifies boot identity,
certificate continuity, permissions, monotonic startup ordering and app health.

Inspect `systemctl show postgresql-tls-prepare podman-authentik-postgresql -p After -p Requires`
and coordinate an operator-approved reboot to verify startup ordering. Never
reboot implicitly. Record evidence (timestamps, fingerprints, test outcomes; no
secrets) under the change, including real-client verification and TLS-only
OpenTofu state access. Only then unblock the separate Garage transport gate.

## Non-destructive recovery

Use container-local `psql` above; the administrative socket is not host-published.
Repair certificate/client settings in automation, re-run preparation, and inspect
PostgreSQL logs after HUP. A reload signal succeeding does not prove PostgreSQL
accepted new material: verify a fresh connection and journal. Keep data/roles and
passwords unchanged. Never initialize or remove the data directory or use the
Authentik disable/cleanup path for recovery. A known-good pair can be restored
through reviewed automation after validating that it remains valid. Reopening
plaintext requires an explicit operator decision and re-blocks Garage; do not
silently set `sslmode=disable`, `require`, or skip hostname verification.
