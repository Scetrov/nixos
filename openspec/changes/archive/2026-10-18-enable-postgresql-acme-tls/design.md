## Context

Habiki's shared PostgreSQL 17 container serves Authentik, Miniflux and OpenTofu state. OpenTofu and Miniflux explicitly disable TLS; Authentik connects over the private Podman network. The existing `scetrov.live` ACME certificate covers `*.net.scetrov.live`.

This change adds verified TLS to that instance and its TCP consumers, unblocking the separate Garage state-transport prerequisite. Other database instances, upgrades, proxies, mTLS, password rotation and a general certificate-distribution framework are out of scope.

## Decisions

### Native TLS and verified clients

Configure PostgreSQL itself on its existing ports. Manage authentication rules for the populated cluster, not just first-initialization scripts: reject non-TLS TCP after cutover and preserve restricted Unix-socket administration and existing password authentication.

Use `habiki.net.scetrov.live:5433` for host/network clients, including Miniflux and OpenTofu. Add the private Podman alias `postgres.net.scetrov.live:5432` for Authentik server/worker, preserving direct container connectivity without a new published endpoint. Add host-side discovery only if needed, following repository DNS conventions.

Use `verify-full` or equivalent with trusted CA roots available in each actual runtime. Confirm the deployed Authentik settings and OpenTofu driver's trust handling before choosing parameters. Regenerate Miniflux's encrypted URL through existing Vault/agenix automation; keep all OpenTofu operations behind `scripts/tofu.sh` and preserve its credential-free modes.

### One certificate handoff service

Use a small PostgreSQL-specific systemd preparation service and ACME renewal hook. Copy only the chain and key into a restricted directory, validate the pair before publishing it, and mount the directory read-only into PostgreSQL. Determine ownership from the actual container identity; do not weaken shared ACME permissions or mount individual files that may retain stale inodes.

Order preparation before database startup. On renewal, publish a consistent pair and reload PostgreSQL without restarting it. Report errors through existing service logging; reject invalid replacements without overwriting the working pair. A reload failure requires operator investigation, not automatic TLS downgrade or a custom rollback manager. Verify the served replacement certificate during the operational renewal check rather than building a per-renewal probing subsystem.

Preserve existing Caddy hooks and keep ACME issuance independent of Authentik/database access. Reusing the wildcard key adds PostgreSQL as a trusted consumer; the dedicated restricted copy bounds that exposure.

## Migration and Verification

1. Inventory TCP consumers, authentication rules, certificate coverage, client TLS support and container identity.
2. In one planned maintenance operation, use targeted Habiki automation to prepare certificates and enable native TLS, migrate and verify clients, then reject plaintext TCP. Do not leave an indefinite mixed-mode deployment.
3. Verify real Authentik server/worker, Miniflux and wrapper-only OpenTofu access, application health, plaintext rejection and local socket administration.
4. Exercise renewal and confirm a fresh connection serves the replacement certificate without a database restart. Check startup ordering and coordinate reboot verification with the operator.

Keep automated regression coverage focused on configuration for an existing cluster, verified/invalid connections, key permissions, invalid-pair rejection and wrapper local modes. Real-client cutover, renewal and reboot checks belong in the short operator runbook; they do not each require a bespoke test harness.

Recovery preserves data, volumes, roles and credentials. Use local socket administration to repair certificate/client configuration or restore a known-good pair. Reopening plaintext requires an explicit operator decision and leaves the Garage transport gate unresolved.

## Compatibility Checks

Resolve before enforcement: deployed Authentik TLS parameters, OpenTofu CA handling, container UID/GID mapping, existing authentication policy and any additional maintenance TCP consumers. These checks do not expand scope.
