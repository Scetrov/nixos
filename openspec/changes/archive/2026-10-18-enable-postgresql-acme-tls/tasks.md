## 1. Confirm compatibility

- [x] 1.1 Inventory shared-instance TCP consumers and authentication rules; confirm client TLS/CA support, certificate coverage and container identity.

## 2. Implement TLS

- [x] 2.1 Add the restricted certificate directory, read-only mount and small preparation/renewal service with pair validation, startup ordering and PostgreSQL reload.
- [x] 2.2 Configure native TLS and existing-cluster authentication rules, preserving socket administration and supporting a bounded cutover to TLS-only TCP.
- [x] 2.3 Add the private certificate-covered Podman alias; migrate Authentik server/worker, OpenTofu, Miniflux and remaining TCP consumers to verified TLS through existing secret workflows.

## 3. Validate and cut over

- [x] 3.1 Add/run focused regression tests for existing-cluster configuration, verified and invalid connections, key permissions, invalid-pair rejection and credential-free wrapper modes; run relevant quality gates.
- [x] 3.2 Write a short runbook covering endpoints, trust, targeted cutover, renewal and non-destructive socket-based recovery.
- [x] 3.3 Perform the targeted Habiki cutover in a planned maintenance window: enable TLS, migrate/verify real clients, enforce plaintext rejection and confirm application health and socket access.
- [x] 3.4 Exercise renewal and verify the served replacement certificate without restarting PostgreSQL; check startup ordering, coordinate reboot verification and confirm Caddy remains functional. Record protected-state evidence for the separate Garage change.

## 4. Finish

- [x] 4.1 Run configured pre-commit and strict OpenSpec validation, inspect/stage intended non-secret changes, and archive the completed change before any requested final signed commit/PR.
