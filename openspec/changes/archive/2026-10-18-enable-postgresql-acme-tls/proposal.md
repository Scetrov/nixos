## Why

The shared PostgreSQL instance accepts unencrypted connections, and OpenTofu and Miniflux explicitly disable TLS. Protect all TCP traffic to this instance using the existing ACME wildcard certificate, resolving the state-transport prerequisite for the Garage broker without expanding that change.

## What Changes

- Enable native PostgreSQL TLS in Habiki's existing `authentik-postgresql` container using the `scetrov.live` ACME certificate covering `*.net.scetrov.live`.
- Migrate every TCP client of this instance, including OpenTofu, Authentik server/worker, Miniflux and maintenance tooling, to certificate-chain and hostname verification (`verify-full` or equivalent).
- Reuse `habiki.net.scetrov.live` for host/network clients and add a certificate-covered private Podman DNS alias for container clients without routing them through the host port.
- Deliver only the required certificate/key with restricted permissions, and reload PostgreSQL after renewal through existing ACME/systemd automation.
- **BREAKING**: Reject all plaintext TCP connections after clients migrate; preserve local Unix-socket administration and recovery.
- Add focused tests and operational documentation for migration, renewal and recovery.

## Capabilities

### New Capabilities

- `shared-postgresql-tls`: Verified TLS for all TCP clients of the shared database, TLS-only server admission, protected ACME certificate delivery and renewal.

### Modified Capabilities

None. Existing application behaviour and database ownership requirements remain unchanged.

## Impact

Touches the existing Authentik PostgreSQL/container configuration, ACME renewal integration, client connection settings, Miniflux encrypted-secret rendering, maintenance tooling where it uses TCP, focused tests and documentation. Preserve databases, roles, passwords, volumes, ports and existing application authentication. All OpenTofu operations remain behind `scripts/tofu.sh`, including credential-free local checks.

Scope is only the shared `authentik-postgresql` instance and its clients. Other PostgreSQL instances, database upgrades, proxies, client certificates, new backup systems and a general certificate-distribution framework are excluded. No new software dependency is intended. The Garage change remains separate and blocked until protected state access is verified.
