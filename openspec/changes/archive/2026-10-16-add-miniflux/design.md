## Context

Habiki runs Caddy, Authentik, PostgreSQL containers, and centralized monitoring. Its inventory selects NixOS 26.05, which provides `services.miniflux`. The existing `authentik-postgresql` container publishes PostgreSQL on host port 5433 and already hosts OpenTofu state in addition to Authentik data. It is application-owned infrastructure, not a general-purpose host PostgreSQL module.

The operator wants one private Miniflux account at `https://feed.net.scetrov.live`. Existing OPML is sufficient for disaster recovery; other application data can be lost. Repository rules require automated provisioning, Authentik access control, runtime secrets, and Grafana observability.

## Goals / Non-Goals

**Goals:**
- Native Miniflux on Habiki, behind Caddy HTTPS, with no directly exposed application port.
- Dedicated database and restricted role in the existing Authentik PostgreSQL instance.
- Native Authentik OIDC restricted to the operator, with no local-login alternative.
- Repeatable first deployment, reconfiguration, secret rotation, and OPML recovery.
- Useful private metrics and centralized logs without exposing feed contents or credentials unnecessarily.

**Non-Goals:**
- PostgreSQL backups, point-in-time recovery, or preservation of read state, saved articles, preferences, sessions, and API credentials after disaster recovery.
- Multiple reader accounts, public registration, a new database server, or an OCI Miniflux runtime.
- Refactoring Authentik PostgreSQL into a general shared-database platform.
- A new dashboard project or a new external network exposure policy.

## Decisions

### 1. Wrap the upstream native service

Add a repository integration module with an explicit Habiki enable flag, importing it from the device configuration. Use `services.miniflux`, disable its automatic local PostgreSQL creation, and select a free loopback HTTP port after checking the existing port inventory. Set the public base URL to `https://feed.net.scetrov.live`.

Verify upstream module behavior for migrations, dynamic service users, and credentials against the deployed channel before relying on it. Check the latest applicable released Miniflux version and the seven-day non-critical update deferral rule. Any package override must pin immutable source content with its cryptographic hash rather than introducing another floating channel.

Alternative: OCI Miniflux matches existing container patterns but adds image/network lifecycle without a demonstrated benefit for this small Go service.

### 2. Share the database server, not database privileges

Connect to `127.0.0.1:5433` using a dedicated `miniflux` database and login role. Grant only the database/schema ownership needed for its own migrations; do not grant superuser, role creation, or database creation privileges to the application. Never use the Authentik administrator credential in the Miniflux process.

Provision and reconcile the database through an idempotent automated systemd setup unit using local administrative container access. Order it after `podman-authentik-postgresql.service` and secret availability, and order Miniflux after successful setup. Bound readiness waits and fail closed on SQL errors. Use safely quoted SQL parameters and avoid credentials in command arguments or logs. Repeated deployment must preserve existing data, reconcile password rotation, and not recreate or drop the database. Automatic application restart/recovery must tolerate a later database container restart without repeatedly performing destructive setup.

Set a modest connection budget appropriate to one reader, and do not widen the database port's existing network exposure. Changing the existing PostgreSQL listener or migrating its other consumers is outside scope.

Alternative: native host PostgreSQL offers peer authentication and isolation but adds another instance. Shared PostgreSQL accepts coupled maintenance and resource contention in exchange for less infrastructure.

### 3. Native OIDC with provider-side authorization

Provision an Authentik confidential OIDC provider and application through OpenTofu, with strict redirect URL `https://feed.net.scetrov.live/oauth2/oidc/callback`. Bind application access to a dedicated operator-only group, preserving existing user/group memberships and denying users outside that group. Require the binding rather than assuming successful Authentik authentication implies authorization.

Configure Miniflux with OIDC, automatic OIDC account creation for the authorized operator, and local authentication disabled. Use the provider's issuer/base URL for `OAUTH2_OIDC_DISCOVERY_ENDPOINT`; Miniflux appends the discovery suffix. The first authorized sign-in creates the reader account without an interactive local-admin bootstrap. Administrative role assignment, if needed for normal operation, must be established through supported, automated mechanisms after verifying current Miniflux behavior; do not assume OIDC groups map to Miniflux administrator privileges.

Caddy performs TLS termination and reverse proxying, not blanket `forward_auth`. This leaves API requests using Miniflux-native credentials rather than HTML login redirects. No API-token provisioning is required initially. Disabling local browser login does not imply disabling Miniflux's authenticated APIs. Existing sessions/tokens have their own lifetime; immediate revocation through an Authentik group change is not promised.

Alternative: proxy-header authentication would add trusted-header boundaries and complicate API clients; native OIDC already fits the service.

### 4. Runtime secrets and ordered first deployment

Database credentials originate in Ansible Vault and are rendered as encrypted agenix inputs. Authentik provider client IDs/secrets originate in OpenTofu outputs, following the existing generated-secret workflow; they must not be independently invented in Vault. Consume generated outputs through restricted runtime files, rejecting missing, empty, or placeholder values before service configuration. Never commit generated plaintext secrets.

Use Miniflux's supported `DATABASE_URL_FILE` and OIDC `*_FILE` settings, or protected runtime environment files where module compatibility requires them. Validate precedence against upstream defaults so an inherited `DATABASE_URL` cannot override the intended runtime secret. Respect dynamic-user and systemd credential-access semantics. Rotation must restart/reconfigure consumers and reconcile the database role before application startup.

All OpenTofu commands run through `scripts/tofu.sh`. A targeted `./scripts/play.sh --limit habiki --tags miniflux` flow must establish Authentik resources and authoritative generated outputs before rendering consumer secrets and rebuilding the host. Existing infrastructure is a prerequisite; initial whole-host bootstrap remains the platform workflow.

### 5. Reuse HTTPS, DNS, and observability

Add a Caddy virtual host using the existing wildcard certificate and a `feed.net.scetrov.live` alias on Habiki in `local-networking.nix`; Blocky already reads `/etc/hosts`. Do not make a new architectural dependency on Grafana: account for the current Caddy module's Grafana guard when placing the service's virtual host, avoiding a broad unrelated refactor.

Enable Miniflux Prometheus metrics and scrape via loopback. Explicitly deny `/metrics` through the public Caddy host: loopback-source filtering alone is insufficient when the reverse proxy itself is local. Preserve journal collection through Alloy and add consistent service labels where needed. Add basic sustained service-down/scrape-failure alerts and verify alert routing through the existing Grafana stack. Feed-fetch failures are not necessarily service outages; use bounded, actionable signals rather than alerting on every publisher failure.

### 6. OPML-only recovery is an accepted loss boundary

Document recovery as automated database/service reprovisioning, authorized OIDC sign-in, and operator OPML import through Miniflux's supported interface. No database backup job is added. Explicitly document state loss and the need to recreate application API credentials after a reset. Keep OPML exports under operator control; they can contain sensitive feed URLs.

## Risks / Trade-offs

- [Shared database outage affects identity and feeds] → Accept coupled availability; use separate roles, bounded connection use, and non-destructive provisioning.
- [Native service rollback does not undo SQL migrations] → Validate upgrade compatibility; retain the database on rollback and do not automatically downgrade or reset schemas. An incompatible rollback requires an explicit operator recovery decision.
- [Incorrect OIDC policy allows other users to enroll] → Explicit operator-only application binding, deny-path tests, and no local registration/login path.
- [Stale generated OIDC secrets break first deployment] → Provision provider first, validate authoritative outputs, and verify redacted credential consistency.
- [Proxy makes metrics appear to come from loopback] → Deny metrics at Caddy and test externally as well as through the private scrape.
- [Feed URLs can target internal services] → Single trusted user is the accepted trust boundary for this change; do not claim Authentik provides outbound SSRF protection. Revisit outbound restrictions before adding users or untrusted subscription automation.
- [Lost application data] → Explicitly accepted OPML-only recovery; no hidden backup guarantees.

## Migration Plan

1. Validate the deployed NixOS module/package, current release/security status, free application port, OIDC claims, and existing secret orchestration.
2. Add regression coverage and automation for provider/policy creation, generated outputs, runtime secrets, database reconciliation, and the native service.
3. Evaluate the NixOS configuration and run relevant tests, lint, secret checks, and configured pre-commit gates.
4. Deploy only to Habiki using the Miniflux tag after previewing the OpenTofu plan through the secure wrapper.
5. Verify database isolation, successful OIDC login, denial for unauthorized identity, local-login disablement, HTTPS/DNS, private metrics, journal ingestion, feed fetching, and repeated deployment. The operator imports OPML and performs any interactive sign-in checks.
6. Roll back by disabling/removing the Miniflux runtime, proxy route, DNS alias, scrape/alerts, and Authentik resources through automation. Retain the dedicated database and role by default until the operator explicitly authorizes deletion; do not disturb Authentik or OpenTofu databases. Never silently reset data to make a rollback succeed.
7. Archive the completed OpenSpec change before final commit/PR.

## Open Questions

- Resolve the exact runtime port, eligible pinned package version, and current module credential semantics during implementation discovery.
- Confirm the existing operator identity and suitable stable authorization selector without embedding sensitive identity details in this proposal.
- Verify whether ordinary reader operation needs any administrative bootstrap beyond OIDC account creation; do not add a local-password login unless the design is explicitly revisited.

## References

- https://miniflux.app/docs/configuration.html
- https://miniflux.app/docs/database.html
- https://miniflux.app/docs/howto.html
- https://github.com/NixOS/nixpkgs/blob/nixos-26.05/nixos/modules/services/web-apps/miniflux.nix
