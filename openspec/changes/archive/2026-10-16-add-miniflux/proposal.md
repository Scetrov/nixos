## Why

Provide a private, self-hosted feed reader at `https://feed.net.scetrov.live` using the stack's existing HTTPS, identity, database, and observability infrastructure. The service is for one operator, who accepts OPML-based disaster recovery and loss of other Miniflux state.

## What Changes

- Run Miniflux as a native NixOS service on Habiki, with an HTTP listener bound only to loopback.
- Reuse the existing `authentik-postgresql` instance with a dedicated Miniflux database and least-privileged login, provisioned and reconciled through automation.
- Publish the service through Caddy using the existing wildcard certificate and local DNS patterns.
- Provision native Authentik OIDC integration with access restricted to the operator; disable local Miniflux login without placing an interactive proxy-authentication gate in front of API clients.
- Manage database and OIDC credentials through Ansible Vault and agenix, never through plaintext repository or Nix-store values.
- Add service logs, private Prometheus metrics, and basic operational alerts to the existing observability stack.
- Provide targeted deployment, verification, OPML recovery, and rollback documentation. Do not introduce PostgreSQL backups or a guarantee of restoring read history, saved articles, preferences, or credentials.

## Capabilities

### New Capabilities

- `miniflux-private-service`: Native runtime, shared-database lifecycle, Caddy/DNS publication, operator-only OIDC access, secrets, observability, and OPML-based recovery.

### Modified Capabilities

None. Existing identity, proxy, and monitoring facilities are extended without changing their established contracts.

## Impact

- Habiki device configuration and a new Miniflux NixOS integration module.
- Caddy virtual hosts, local networking aliases, and existing PostgreSQL service ordering/provisioning automation.
- Authentik OpenTofu resources, secret export/injection workflows, Ansible secret generation, and targeted deployment tags.
- Alloy/Prometheus configuration, alert rules, regression tests, and operator documentation.
- New dependency on the native Miniflux package; implementation must verify the latest applicable released version, integrity pinning, and the repository's seven-day deferral policy for updates without a CVSS >= 7 fix.
- No deployment, database modification, or application implementation is performed by this proposal.
