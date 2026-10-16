# Private Miniflux on Habiki

Miniflux runs natively at **https://feed.net.scetrov.live**, behind Caddy on
`127.0.0.1:8091`. It uses a dedicated `miniflux` database/role in the existing
`authentik-postgresql` container (`127.0.0.1:5433`). No separate database server,
public application port, local-password account or PostgreSQL backup job is added.

## Deploy

Prerequisites: the existing Habiki/Authentik/PostgreSQL/Caddy/ACME stack, Vault
access and the confirmed `scetrov` Authentik identity. Review the working tree:
a NixOS switch activates the entire declarative host, not only one service.

```sh
# Preview the same dependency graph that the targeted workflow provisions.
./scripts/tofu.sh -- plan -target=authentik_policy_binding.miniflux_access

# After reviewing the plan, provision identity, refresh encrypted generated
# outputs, render/copy age secrets and activate Habiki in that order.
./scripts/play.sh --limit habiki --tags miniflux
```

The identity target includes its provider/application, dedicated group, binding
and credential dependencies, not unrelated application changes. The wrapper's
successful apply refreshes `src/generated-secrets.yml` before Ansible loads it.
Do not use `--skip-generated-refresh` for this tag. First installation must use
this workflow rather than a standalone `nixos-rebuild` or a generic generated
secret refresh: the new OIDC outputs do not exist before provider provisioning.

The Miniflux-only tag keeps existing channels and skips unrelated blanket Podman
restarts, Frontier writer stops, Headscale enrollment and Garage provisioning.
NixOS itself may restart other units if the checked-out host configuration changes.
`-- --check`, `-- --syntax-check` and list modes do not apply OpenTofu changes.

The shared `local-networking.nix` adds the alias on every device when deployed.
Habiki's rebuild reloads Blocky. If clients also use Fyne's DNS, propagate that
same alias using the existing DNS-only workflow (a separate, explicit target):

```sh
./scripts/play.sh --limit fyne --tags local-dns
```

Verify both resolvers return `10.229.10.2`; DNS caches may retain earlier NXDOMAIN
answers. The Habiki-only tag intentionally does not deploy to Fyne or other hosts.

## Access and trust boundary

The confidential Authentik OIDC provider registers only
`https://feed.net.scetrov.live/oauth2/oidc/callback`. Its application requires
membership in **Miniflux Operator**, whose sole configured member is the existing
`scetrov` identity. Other group memberships are left unchanged. An authorized
first login creates a normal reader account; local login and admin bootstrap
are disabled. Caddy does not impose browser authentication on API requests.

Create personal API credentials in Miniflux after sign-in if needed. Protected
API calls must fail without native credentials and succeed with a valid token
without requiring an Authentik browser session. Do not paste credentials into
shell arguments or logs. Group removal prevents subsequent OIDC authorization;
it does not promise immediate revocation of existing Miniflux sessions/tokens.

This is a **single trusted user's outbound-fetch service**. Feed URLs and OPML
can reference private networks or contain embedded credentials. Authentik is not
an outbound SSRF firewall. Revisit outbound isolation before admitting additional
users or untrusted subscription automation.

## Credentials and rotation

- Database password: `miniflux_db_password` in encrypted `src/secrets.yml`.
  `scripts/provision_miniflux_vault.py` creates it once and never silently rotates it.
- OIDC ID/secret: authoritative provider outputs, exported by `scripts/tofu.sh`
  into encrypted `src/generated-secrets.yml`; do not invent duplicate Vault values.
- Agenix material is root-only (`0400`). systemd `LoadCredential` exposes only
  required files to the dynamic Miniflux user. No secret is embedded in Nix
  configuration, command arguments, or the store as plaintext.

Rotate the database password with Ansible Vault, then rerun the targeted workflow.
The setup unit reconciles the role before restarting Miniflux. For OIDC rotation,
preview a replacement of `random_password.miniflux_client_secret` through
`scripts/tofu.sh -- plan -replace=random_password.miniflux_client_secret`, then
apply the reviewed replacement through the wrapper and rerun the targeted flow.
An OIDC rotation has a brief provider/consumer mismatch until activation.

`scripts/verify_miniflux_oidc.py` compares authoritative OpenTofu JSON on stdin
with runtime credential files using constant-time comparison and prints only
pass/fail. Run it with permission to read the consumer's actual credential files;
retrieve outputs only through `scripts/tofu.sh`. Do not print, persist or put raw
JSON/credentials into arguments. Live consistency still needs post-deploy checking.

## Health and observability

- `systemctl status miniflux miniflux-dbsetup` checks service/setup state.
- Private metrics: `http://127.0.0.1:8091/metrics`, scraped every minute with
  `job="miniflux", service="miniflux"`; Caddy denies `/metrics*` on the public host.
- Alloy journal ingestion labels `miniflux.service` and `miniflux-dbsetup.service`
  as `service="miniflux"`. Miniflux uses warning-level logging; avoid debugging
  publisher content or credentials into centralized logs.
- Grafana provisions `MinifluxServiceUnavailable` after five minutes of failed
  or missing scrapes/query availability, using the existing Mimir datasource and
  default notification policy. Receiver delivery must be verified after deployment;
  this change does not replace contact points or the shared routing tree.

Shared database maintenance/outages affect both identity and feeds. Setup has
bounded readiness/SQL timeouts and blocks initial application startup on failure.
An already-running service uses its normal restart/reconnect path after database
restarts. Provisioning never drops/recreates existing data to recover availability.

## OPML-only recovery

Export OPML from Miniflux's subscription/export interface after subscription
changes and keep it in operator-controlled storage. Import existing OPML through
the authenticated import interface after a fresh OIDC sign-in. Treat exports as
sensitive because feed URLs may contain private information or credentials.

After actual database loss, reprovision through the same targeted automation,
sign in through OIDC, and import OPML. An empty database is automatically created
only if absent. **Do not drop an existing database as an ordinary recovery step.**
Any deliberate destructive reset requires separate operator approval and reviewed
automation restricted to the Miniflux database.

OPML restores subscriptions, not read history, saved articles, preferences,
sessions, or old API credentials. Recreate API credentials and update clients.
There is no database backup, point-in-time recovery or hidden state-restoration
guarantee in this deployment.

## Non-destructive rollback

1. Disable `scetrov.services.miniflux.enable` in Habiki and set inventory
   `miniflux_enabled: false`. Deploy the host configuration through automation.
   The module removes runtime/setup units, the Caddy host and private scrape.
   Grafana receives an explicit `deleteRules` entry for the service alert.
2. Remove the feed alias from shared `local-networking.nix` and apply the DNS-only
   workflow to both existing DNS hosts. Check no feed route, scrape or alert remains.
3. Remove the Miniflux-only OpenTofu resources/outputs in `terraform/miniflux.tf`
   and their two mappings in `scripts/render_generated_secrets.py` together.
   Preview and apply through `scripts/tofu.sh`; this removes the provider,
   application and access group without modifying unrelated memberships. Do not
   use the Miniflux deployment tag after removing its identity resources.
4. Remove only Miniflux age declarations/rendering and encrypted consumer inputs
   when no longer needed; remove the Vault entry only after deciding whether
   retained database access will still be needed.

**Retain the Miniflux database and role by default.** No rollback unit deletes
them. Authentik and OpenTofu state databases must remain untouched. NixOS rollback
does not reverse Miniflux SQL migrations: never silently reset or downgrade the
schema to make an older package start. An incompatible downgrade requires an
explicit operator recovery decision, potentially accepting OPML-only recovery.
