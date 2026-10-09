# Private Forgejo (Habiki)

Operational runbook for the private Forgejo Git forge on Habiki.

## Architecture

- Service: native NixOS `services.forgejo` (Forgejo 16.0.5, SQLite) owned by the `forgejo` user.
- HTTPS: `https://source.net.scetrov.live` through the shared Caddy listener (`scetrov.live` wildcard certificate). The virtual host admits only the private source networks and denies the internal `/metrics` and `/api/internal` routes.
- Git SSH: Forgejo built-in SSH on TCP `2222`, source-scoped to the private networks on both iptables and nftables. Administrative SSH on 22 is untouched. Clone form: `ssh://git@source.net.scetrov.live:2222/<owner>/<repo>.git`.
- Identity: native Authentik OIDC (`authentik` authentication source), restricted to members of the `Forgejo Owners` group. Open registration, anonymous repository access, and local password sign-in are disabled.
- Storage: `/var/lib/forgejo` (SQLite database, repositories, attachments, built-in SSH host key). No high availability, no formal backup guarantee.
- Observability: journal logs flow to central Loki under `service=forgejo`; `/metrics` is bearer-token protected and scraped privately by Prometheus (job `forgejo`); a `ForgejoServiceUnavailable` Prometheus alert rule and the `Forgejo Service` Grafana dashboard surface availability.
- Actions: **disabled and deferred**. `scetrov.services.forgejo.runner.enable` stays `false` on Habiki; no runner account, units, timer, or egress rules exist. Retained experimental runner code is future-work reference only.

## Deployment

### Targeted Habiki deployment (consumer path)

```bash
./scripts/play.sh --limit habiki --tags forgejo
```

This single documented path sequences:

1. Pre-flight refresh of the OpenTofu-generated OIDC outputs into `src/generated-secrets.yml` (fail-closed validation).
2. The `secrets` role: encrypts and deploys the Forgejo OIDC credentials and the metrics token through agenix, and renders the NixOS modules.
3. The `nixos` role: rebuilds the host (Forgejo unit, Caddy route, source-scoped SSH rules).
4. Identity reconciliation: the `forgejo.service` `preStart` reconciles the native OIDC authentication source and owner administration *before* the web process starts, using the systemd credential files. There is no separate undocumented deployment step and no runner registration or first-login gate.

### First deployment (identity prerequisites first)

The generated Forgejo OIDC outputs do not exist until the shared Authentik
plan has been applied. Before the first consumer deployment:

1. Review the shared OpenTofu plan (blast radius includes existing applications) via the secure wrapper:

   ```bash
   ./scripts/tofu.sh -- plan
   ```

2. Apply it once the field-level review passes (this also refreshes `src/generated-secrets.yml`):

   ```bash
   ./scripts/tofu.sh
   ```

3. Then run the consumer deployment above. If the generated values are still
   missing or placeholders, the `secrets` role fails closed with an explicit
   message before any consumer configuration is rendered.

### Fyne DNS-only rollout

`source.net.scetrov.live` is resolved by the shared Blocky configuration on both DNS servers. Deploy the alias to Fyne without deploying Forgejo there:

```bash
./scripts/play.sh --limit fyne --tags local-dns
```

Query both Blocky servers after rollout to confirm they answer
`source.net.scetrov.live → 10.229.10.2`.

## Owner access management

- Admission is by Authentik group membership: the `Forgejo Owners` group (currently only `scetrov`). The OIDC source grants Forgejo administration from that signed claim; email strings are never used for authorization.
- To admit or remove a member, change the group in the managed Authentik configuration and re-run the Authentik deployment path. OIDC auto-enrollment creates the Forgejo account on first sign-in; removing a member does **not** immediately revoke existing Forgejo sessions, SSH keys, or tokens (see revocation below).

## Credential and session lifecycle

- **OIDC client secret rotation**: re-run the OpenTofu apply (via `./scripts/tofu.sh`) and the consumer deployment. The `forgejo` unit restart triggers on the credential file changes and the `preStart` reconciliation updates the authentication source in one run. No second undocumented deploy is required.
- **Metrics token**: `forgejo_metrics_token.age` is generated once by the secrets role and reused; it is shared between the Forgejo `metrics.TOKEN` credential and the Prometheus `bearer_token_file`. Regenerate by deleting `src/roles/secrets/files/secrets/forgejo_metrics_token.age` and re-running the secrets path.
- **Revoke a user**: disable or delete the Forgejo account (admin UI or `admin user` CLI), which ends sessions and blocks sign-in; separately delete their registered SSH keys and API/Git HTTPS tokens. Dismissing the user from the Authentik group blocks new sign-ins but does not perform these revocations.
- **Git credentials**: SSH keys and API tokens are service-native; manage them per user in Forgejo.

## Observability

- Grafana: `Forgejo Service` dashboard (`svc-forgejo`, Operations / Services) — availability stat, release, request rate, forge state, and `service=forgejo` logs, using the repository palette.
- Alerting: `ForgejoServiceUnavailable` (Prometheus, 5m) fires when the private `127.0.0.1:3002/metrics` scrape fails for five minutes.
- The `/api/healthz` endpoint (database/cache ping) is the service's own health signal; it is not exposed through the public virtual host.

## Disable, rollback, and data retention

- **Disable**: set `scetrov.services.forgejo.enable = false` on Habiki and rebuild. This removes the service, the Caddy route, and the SSH 2222 firewall rules while **preserving** `/var/lib/forgejo` (state, repositories, SSH host key) and the Authentik resources. Disabling and state removal are separate operations; nothing in this path deletes data.
- **Rollback**: redeploy the previous configuration via the same targeted path. If reverting a Forgejo upgrade that migrated the SQLite schema, do **not** assume the older binary can read the migrated database; restore a compatible snapshot instead.
- **Pre-upgrade snapshots**: before upgrades that may migrate schemas, take a consistent manual snapshot (stop the service, copy `/var/lib/forgejo` preserving permissions, and restore with an explicit approval when schema-compatible). No formal backup guarantee is provided.

## Access boundaries (verified at acceptance)

- Allowed sources for HTTPS and SSH 2222: `10.229.0.0/16`, `100.64.0.0/10`, `fd0b:281e:d657:3ca1::/64`, `fd7a:115c:a1e0::/48`. All other peers receive 403 (HTTPS) or are dropped (SSH).
- No public DNS record, no router port forwarding, no Headscale route or ACL changes.
