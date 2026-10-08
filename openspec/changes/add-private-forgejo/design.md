## Context

Habiki already hosts Caddy, Authentik, Prometheus, Loki, Grafana, and multiple services. Service configuration is synchronized and rebuilt through Ansible. `local-networking.nix` is imported by Habiki and Fyne; Blocky reads `/etc/hosts`, so a shared alias becomes an answer from both local DNS servers after deployment. The existing ACME certificate includes `*.net.scetrov.live`.

The owner confirmed that Headscale clients already reach LAN IPs and resolve local DNS names. Teleport and Headscale are existing private access paths, not new networking projects. Forgejo will hold personal code and experiments; Actions/CI is deferred; there is no requirement for public DNS, HA, or formal recovery guarantees. Existing services and administrative SSH must remain unaffected.

## Goals / Non-Goals

**Goals:**
- Private Forgejo HTTPS at `source.net.scetrov.live` and Git SSH on TCP 2222.
- Native Authentik OIDC restricted initially to the owner.
- SQLite and persistent repositories across routine rebuilds/restarts.
- Actions disabled; experimental runner code retained without deployment activation.
- Declarative, repeatable installation, identity configuration, and secret rotation.
- Basic logs, metrics, and service-health visibility through the existing observability stack.

**Non-Goals:**
- Public DNS records, router port forwards, public anonymous repository hosting, or open registration.
- Actions/CI, runner registration/runtime deployment, job images/actions, and job observability.
- High availability, production SLAs, or a formal backup service.
- Migrating existing repositories or changing Headscale route/ACL policy.

## Decisions

### 1. Prefer native NixOS service integration with a small repository module

Use the supported NixOS Forgejo service module if its available release and options satisfy the required HTTP, SSH, SQLite, OIDC reconciliation, and metrics behavior. Put repository-specific options and glue in a Forgejo module imported/enabled by Habiki. Verify actual package versions, release compatibility, and module APIs before choosing implementation details.

This reduces custom container startup and database orchestration. An OCI Forgejo deployment remains an implementation fallback if the native module cannot satisfy supported-version requirements; it must preserve the same network, state, and secret contracts. Package sources must carry Nix integrity hashes; any OCI images must use fully qualified digest-pinned references. Resolve versions during implementation and apply the repository's seven-day deferral for updates without CVSS >= 7.0 fixes.

### 2. Terminate HTTPS at Caddy; keep service listeners private

Set Forgejo's external root URL to `https://source.net.scetrov.live/` and proxy to a non-conflicting loopback-only HTTP port. Use the existing `scetrov.live` ACME host. Trust forwarded identity/network information only from the actual proxy; do not put Authentik `forward_auth` in front of the forge.

Restrict the Forgejo virtual host to verified private access paths, including their observed VPN source addresses, and restrict SSH similarly. Account for IPv6 and avoid an unrestricted SSH firewall opening. Reuse the shared HTTPS listener rather than add public-facing listeners or router forwarding. Local-only DNS alone is not an authorization control: the hostname could still be supplied directly to a publicly reachable shared HTTPS listener.

Add `source.net.scetrov.live` to the `10.229.10.2` list in `local-networking.nix`. Deploy that shared configuration to both Blocky hosts; do not deploy Forgejo on Fyne. Existing VPN DNS/routing is assumed functional based on the owner's confirmation and must be verified at acceptance time. Any missing VPN routing or ACL changes require separate agreement rather than silently broadening this change.

### 3. Use separate Git SSH on port 2222

Use Forgejo's supported dedicated SSH listener (built-in SSH where supported), advertise `source.net.scetrov.live` and port 2222, and keep host administrative SSH unchanged. Expected clone form: `ssh://git@source.net.scetrov.live:2222/<owner>/<repo>.git`.

SSH keys are registered with Forgejo and authenticated by Forgejo, independently of interactive OIDC. Protect and preserve the Git SSH host key. Integrating Git access into administrative OpenSSH on port 22 was rejected in favor of less coupling and simpler rollback.

### 4. Use SQLite and preserve useful service state

Keep SQLite, repositories, attachments/LFS if enabled, and service/SSH keys in persistent service-owned directories outside ephemeral job/container storage. No separate PostgreSQL deployment is needed for this workload. Ordinary rebuilds, image changes, and disabling the service must not delete state.

No formal backup promise is introduced. Before upgrades that migrate SQLite or repository formats, document a consistent manual snapshot procedure; rollback must not assume an older binary can read migrated data. Disablement and removal of state are separate operations.

### 5. Native OIDC with owner-only enrollment

Create a dedicated Forgejo access group containing only the owner's confirmed Authentik identity, an OAuth2/OIDC provider, an application, and access binding through OpenTofu. Use authentication-source name `authentik` with strict redirect URI `https://source.net.scetrov.live/user/oauth2/authentik/callback`, subject to verification against the selected Forgejo release. Reuse established profile/email scopes and explicitly configure identity matching and account creation so only the admitted identity can create/sign in to a normal account.

Disable open registration and anonymous access to repository content. Disable normal local-password sign-in where supported without disabling OIDC admission. If a local bootstrap administrator is required, provision it automatically with a vault-backed secret, limit it to bootstrap/break-glass use, and remove or disable routine password access after owner administration is established. Do not grant admin based solely on an unverified email string.

Use a supported CLI/API or native module integration to idempotently reconcile Forgejo's authentication source. Authentik is managed by OpenTofu; Forgejo service-internal state is configured by supported automation rather than UI clicks. Ordinary Git SSH keys and API/Git HTTPS tokens remain service-native credentials. Revoking Authentik access need not immediately revoke issued Forgejo sessions, SSH keys, or tokens; document and test the corresponding Forgejo account-disable/revocation procedure.

### 6. Refresh generated credentials before configuring consumers

Extend the existing generated OIDC outputs pipeline to Forgejo. OpenTofu runs only via `scripts/tofu.sh`. Managed OIDC outputs are authoritative and carried through the existing protected generated-secret and agenix workflow; manually supplied bootstrap/registration material originates in encrypted `src/secrets.yml`. No sensitive value enters the Nix store, committed files, normal task output, intentionally emitted process logs, or CI job environments. **Operator-accepted exception:** Forgejo's standard OIDC administration CLI receives the client secret in runtime argv via `--secret VALUE`; process inspection or argument-capturing monitoring may expose it. The operator accepts this bounded risk rather than maintain a custom package patch. Read the secret from protected runtime files only, disable shell tracing, suppress/redact command output and errors, and never interpolate its value into Nix expressions or generated store scripts. This exception does not authorize argv exposure for other credentials when protected file/stdin interfaces exist.

Use this dependency order: create/reconcile Authentik resources; refresh and validate generated OIDC credentials; encrypt/deploy runtime secrets; rebuild service configuration; reconcile Forgejo identity/bootstrap state. Rotation must update consumer configuration automatically without an undocumented second full deploy. Missing credentials fail closed before consumer rendering, without preventing the prerequisite identity phase from creating them.

Provide a targeted Forgejo tag/path for Habiki that executes this order, alongside a separately targeted DNS configuration deployment to Fyne. Audit the existing role/wrapper order rather than assume the current generic playbook already meets it. Account for any shared Authentik OpenTofu plan affecting other applications before applying it.

### 7. Defer Actions and retain experiments disabled

The operator removed Actions from this change after the checkout/artifact
compatibility investigation. Set Forgejo `actions.ENABLED = false` on Habiki.
Keep experimental runner modules, registration/cleanup helpers, fixtures and
examples for future work, behind an independent default-off runner option;
Habiki explicitly leaves that option false. Enabling Forgejo alone must not
create a runner user, runtime/daemon/cleanup units, timer, registration command,
egress rules or readiness service.

No runner registration, first-login deployment gate, job execution, job-image or
action selection, or job-health acceptance is required for this change. Owner
OIDC first-login remains an access acceptance check, not a prerequisite blocking
deployment completion. Reintroducing Actions requires a separately agreed change
and real end-to-end runtime/DNS/TLS/isolation acceptance; existing experimental
code and earlier probes are not an accepted production CI implementation.
Historical runner requirements are preserved in `deferred-actions.md`.

### 8. Reuse existing observability instead of inventing a platform

Route Forgejo logs through existing journal collection into Loki with stable service labels. Scrape Forgejo metrics privately using authentication if the selected release supports it. Add compact Grafana visibility and health alerts for Forgejo availability using actual discovered metric/log fields and service health. Do not expose metrics through the Forgejo virtual host. Runner/job visibility and alerts are deferred.

## Risks / Trade-offs

- [Private DNS does not make a Caddy route private] → Validate source restrictions for HTTPS and SSH, including IPv6 and actual Teleport/Headscale traffic, without changing unrelated sites.
- [OIDC restriction is not instantaneous SSH/token revocation] → Document explicit Forgejo account disablement and credential/session revocation; do not claim OIDC governs every Git request.
- [First deployment has no generated OIDC outputs] → Separate prerequisite identity generation from consumer configuration and test a clean deployment plus a repeat run and credential rotation.
- [SQLite upgrade may prevent binary-only rollback] → Preserve state and take a consistent pre-upgrade snapshot when schemas change; restore a compatible snapshot only with explicit approval.
- [Both DNS servers may return inconsistent answers during rollout] → Target the shared alias deployment to Habiki and Fyne and query each server explicitly.

## Migration Plan

1. Inspect the selected supported Forgejo release, NixOS options, host capacity, existing listeners, and deployment/secret ordering. Confirm the owner's Authentik identity before granting access.
2. Validate first-deploy/reconcile behavior locally in disposable fixtures or an isolated NixOS test; no live secrets in fixtures.
3. Add declarative identity, runtime secrets, service modules, private routing, SSH, observability, and targeted orchestration.
4. Review the OpenTofu plan through the wrapper, deploy identity prerequisites and generated secrets, then deploy only the Habiki Forgejo path. Deploy the DNS-only host configuration to Fyne separately with an appropriate targeted tag.
5. Verify both DNS servers, trusted TLS, owner-only OIDC, unauthenticated denial, Git SSH clone/push, HTTPS token access, and Actions/runner inactivity. Repeat connectivity checks from Teleport and Headscale clients and test denied sources.
6. Repeat deployment and OIDC credential reconciliation to demonstrate no duplicate auth sources or state loss. Run repository checks/pre-commit as applicable and document operational limitations.
7. Archive this change before the final signed commit/PR. Stage only intended non-sensitive files and use the repository's attribution conventions.

Rollback: disable the Forgejo service, remove the Forgejo Caddy route/SSH opening and alias using automation, and disable the dedicated Authentik application. Preserve data and keys. If reverting an upgrade with migrations, use a consistent compatible snapshot rather than blind binary downgrade. Do not remove shared Caddy, Authentik, DNS, or runtime resources used by other services.

## Open Questions

- Which existing Authentik account is the owner? Resolve during implementation before applying access membership; do not guess from usernames in source control.
- Which supported Forgejo releases are available in the configured Nix channel and satisfy update-age/security policy? Select and verify at implementation time.
- What source addresses do Teleport and Headscale actually present to Habiki, and which private access checks already exist upstream? Observe them before finalizing source restrictions.
- Which real Forgejo metrics/log events and service-health signals are available? Discover before writing health queries and alert rules.
