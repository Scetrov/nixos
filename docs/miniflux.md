# Private Miniflux on Habiki

Miniflux runs natively at **https://feed.net.scetrov.live**, behind Caddy on
`127.0.0.1:8091`. It uses a dedicated `miniflux` database/role in the existing
`authentik-postgresql` container (`habiki.net.scetrov.live:5433`) with verified
TLS (`verify-full` and the host CA bundle). See [shared PostgreSQL TLS](postgresql-tls.md)
for the initial cutover prerequisite, renewal and recovery. No separate database
server, public application port, local-password account or PostgreSQL backup job is added.

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
- Alloy journal ingestion labels `miniflux.service`, `miniflux-dbsetup.service`,
  and the optional subscription plan/apply units as `service="miniflux"`. Miniflux uses warning-level logging; avoid debugging
  publisher content or credentials into centralized logs.
- Grafana provisions `MinifluxServiceUnavailable` after five minutes of failed
  or missing scrapes/query availability, using the existing Mimir datasource and
  default notification policy. Receiver delivery must be verified after deployment;
  this change does not replace contact points or the shared routing tree.

Shared database maintenance/outages affect both identity and feeds. Setup has
bounded readiness/SQL timeouts and blocks initial application startup on failure.
An already-running service uses its normal restart/reconnect path after database
restarts. Provisioning never drops/recreates existing data to recover availability.

## Git-managed subscriptions

`config/miniflux/feeds.json` is the hand-edited authority: 47 sources, currently
37 enabled and ten disabled with reasons. The initial seed had 39 enabled and
eight disabled; two more were disabled after authorized Habiki testing below.
The change's `feed-audit.md` records
point-in-time research, not a guarantee of ongoing ingestion. Edit titles,
categories, public HTTP(S) URLs and `enabled`; disabled entries need a `reason`.
Use `aliases` only for known alternative stored URLs. Keep an old URL as an alias
when changing a catalogue URL; sync does not migrate existing subscriptions.
ZDNet is general news, not a security-only feed.

Offline commands require only Python's standard library and make no requests:

```sh
python3 scripts/miniflux_subscriptions.py validate
python3 scripts/miniflux_subscriptions.py export > /tmp/miniflux.opml
```

Export is deterministic UTF-8 OPML containing enabled feeds grouped by category.
Import through the authenticated Miniflux interface; manual OPML import is a
fallback, not a promise of API-sync idempotency. Never add credentials, signed
URLs, private tokens or personal subscription URLs to the public catalogue.

### Optional token enrollment

1. Sign in through Authentik at `https://feed.net.scetrov.live` as the intended
   operator. In Miniflux's API Keys page (`/keys`), create a personal API key.
   Do not create a local-password/admin user or provision accounts/tokens in SQL.
2. Run `./scripts/visecret.sh` locally and add `miniflux_subscription_api_token`
   to encrypted `src/secrets.yml`. Use an editor configured not to retain swap,
   backup or history files. Never paste the token into chat, shell arguments,
   tracked plaintext or logs. The agent needs only confirmation that it is saved.
3. Set `miniflux_subscriptions_enabled: true` under Habiki in `src/inventory.yml`
   and `scetrov.services.miniflux.subscriptions.enable = true` in
   `src/roles/nixos/files/device-configuration/habiki.nix`. The module's
   `subscriptions.operator` defaults to the exact Miniflux username `scetrov`;
   check it against the signed-in account and configure it explicitly if different.
4. Deploy with `./scripts/play.sh --limit habiki --tags miniflux`. This renders
   the optional Vault token to Habiki-only agenix material, copies the public
   tool/catalogue into `/etc/nixos/modules/`, and activates the two credential-backed
   oneshots. It does **not** sync subscriptions. Review host configuration drift
   first: NixOS activation is host-wide, even with this targeted tag.

Missing enrollment does not affect ordinary Miniflux deployments when both flags
remain disabled. The token never enters the Nix store as plaintext: systemd
`LoadCredential` supplies a private runtime file. systemd may use root-owned
`0440` credentials with an ACL granting only the service UID read access; the tool
accepts that exact ACL layout, not ordinary group/world-readable files. The sync
user is a dedicated system user separate from the reader. Rotate by replacing the Vault value and
redeploying; token changes alone do not invoke either oneshot.

### Explicit plan and apply

Prerequisite: deploy the enrolled Miniflux stack first. No identity provisioning,
secret rendering or host rebuild happens during these commands:

```sh
# Default is read-only: verify operator identity and inventory, then show additions.
./scripts/play.sh --limit habiki --tags miniflux-subscriptions

# After reviewing the plan, opt in to create missing enabled subscriptions.
./scripts/play.sh --limit habiki --tags miniflux-subscriptions -- -e miniflux_subscriptions_apply=true

# Repeat the same apply: known existing subscriptions should produce zero writes.
./scripts/play.sh --limit habiki --tags miniflux-subscriptions -- -e miniflux_subscriptions_apply=true
```

The wrapper requires the sole subscription tag and exact Habiki limit. Check,
syntax and list modes do not invoke sync. Plan and apply share a nonblocking lock;
requests have 60-second timeouts, the tool has a 2400-second execution deadline,
and systemd has a 2500-second startup limit. There is no boot dependency, timer,
automatic restart, or catalogue/credential-triggered reconciliation.

For direct diagnosis **on Habiki**, the equivalent secure commands are
`sudo systemctl start miniflux-subscriptions-plan.service` and
`sudo systemctl start miniflux-subscriptions.service`. They use the same runtime
credentials, identity checks and lock. View their results with
`sudo journalctl -u miniflux-subscriptions-plan -u miniflux-subscriptions`.
Ansible waits for completion, displays that invocation's sanitized journal, and
fails on incomplete execution. Both units receive the existing Alloy/Loki
`service="miniflux"` label; no new metrics or alerts are added.

Apply only creates missing categories and feeds. It never retags, edits or deletes
existing feeds, settings, categories, articles, bookmarks or read markers, including
UI-managed subscriptions. Disabling/removing an entry prevents future creation;
it does not unsubscribe. Code rollback likewise does not undo successful additions.

After an uncertain create, sync re-reads inventory rather than blindly retrying
the POST. Successful additions remain when another entry fails. Inspect the
journal and Miniflux, correct the cause, review a new plan and rerun explicitly.
For unexpected canonical URLs, review native inventory and add a known alias;
do not match by title or invent a replacement. Authentication/identity/inventory
failures stop writes. Publisher parsing and TLS remain Miniflux's responsibility;
do not disable TLS validation to force ingestion.

### Verification evidence

Disposable testing against digest-pinned Miniflux 2.3.3 passed initial creation,
repeat-run zero mutation requests, independent partial failure, a synthetic
approximately 10 MB feed, native OPML import, and fresh-database recovery with a
replacement personal token obtained after a new OIDC login (non-admin account).
Smashing Security and BrakeSec both ingested successfully in that environment.
This is **not** evidence of a completed Habiki apply or ingestion of all sources.

The test fixture initially failed because Miniflux correctly refused its loopback
feed URL. Only the disposable container sets `FETCHER_ALLOW_PRIVATE_NETWORKS=1`;
production retains its default protection. Reproduce the opt-in container test
only with explicit runtime/network authorization:

```sh
nix-shell -p openssl --run 'python3 scripts/tests/run_miniflux_subscriptions_integration.py'
```

It uses ephemeral test OIDC keys, memory-only PostgreSQL and loopback-published
ports, removes its own pod on exit, and accepts no production endpoint or token.
The test images are digest-pinned in the harness.

On 2026-10-17, the authorized Habiki rollout enrolled the operator token, passed
identity verification and a read-only plan, and created **37 of 39 enabled
subscriptions**. All 37 stored feeds initially reported zero parsing errors.
Check Point (`https://blog.checkpoint.com/feed/`) and Security Boulevard
(`https://securityboulevard.com/feed/`) returned publisher HTTP 403 and were not
created. The operator subsequently authorized disabling both pending revalidation;
their original URLs and HTTP 403 reasons remain in the catalogue. No TLS bypass,
automatic replacement or retry loop was added.

The Register was created successfully but stored this observed canonical URL:
`https://api.theregister.com/api/v1/article?orderBy=published&site_id=2&remapper=rss&query=tag:security`.
It is now an explicit catalogue alias, deployed and recognized without duplicate
creation. After deploying the two authorized disablements, both the live plan and
repeat apply succeeded with **37 present, zero missing, zero created and zero
failures**. The earlier partial apply correctly returned nonzero and retained its
successful creations. Ansible reads the latest journal invocation directly because
successful inactive oneshots clear their live `InvocationID`. Regression tests also
cover systemd's root-owned, service-UID-only credential ACL so ordinary group/world
read permissions are not mistaken for a private credential.

### Recovery and non-destructive sync disablement

After actual database loss, reprovision through the normal targeted automation
and sign in through OIDC. Either import catalogue-generated/operator-held OPML,
or create and securely enroll a **replacement** personal token before plan/apply.
A token retained in Vault is invalid after its database is lost. Neither route
restores read history, saved articles, preferences, sessions or prior credentials.
There is no PostgreSQL backup or point-in-time recovery guarantee.

An empty database is created only if absent. **Do not drop an existing database
as an ordinary recovery step.** Any deliberate destructive reset requires separate
operator approval and reviewed automation restricted to the Miniflux database.

To disable only subscription automation, set both enrollment flags to false and
redeploy normally. This removes the credential consumer and both oneshots without
touching the reader, subscriptions, database, routes or identity. Remove the
optional Vault token and its encrypted consumer file through reviewed automation
when no longer needed, and revoke the personal key in Miniflux. Do not invoke the
subscription tag after disabling its units.

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
