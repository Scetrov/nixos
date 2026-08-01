## ADDED Requirements

### Requirement: Codex app-server runs as a declarative Podman workload
The system SHALL run a pinned Codex app-server OCI image on Habiki through NixOS-managed Podman and systemd configuration, using an immutable release version and image content hash or digest.

#### Scenario: Service starts on boot
- **WHEN** Habiki boots with the Codex app-server option enabled
- **THEN** systemd starts the Podman workload automatically and restarts it after an unexpected process failure

#### Scenario: Image provenance is reproducible
- **WHEN** the Codex app-server image is built or deployed
- **THEN** automation resolves the official pinned Codex distribution using repository-recorded integrity data and does not use a floating or unofficial image tag

#### Scenario: Container is least privilege
- **WHEN** the container is inspected after deployment
- **THEN** the Codex process runs as a dedicated non-root identity with no published ports, no workspace or host executable mounts, dropped capabilities, a read-only root filesystem where compatible, and only its declared state and runtime mounts

#### Scenario: Full control surface is isolated
- **WHEN** a caller with control-socket access attempts a non-account app-server method
- **THEN** the container boundary prevents access to host workspaces, host executables, privileged operations, or undeclared writable paths, and validation records any residual quota-consumption risk

### Requirement: Codex app-server is reachable only through a local Unix socket
The system SHALL expose the app-server JSON-RPC control interface through `/run/codex-app-server/control.sock` on Habiki and SHALL NOT expose a TCP listener, Caddy route, Authentik application, or host firewall port. Rootless Podman SHALL run as `codex-app-server` with keep-id mapping and retained membership in the `ai-usage-exporter` access group; the private state directory SHALL be mode 0700, the setgid runtime directory mode 2770, and the socket mode 0660 under umask 0007.

#### Scenario: Exporter connects locally
- **WHEN** the AI usage exporter initiates a Codex collection cycle
- **THEN** it connects to the app-server Unix socket using permissions granted to its service identity

#### Scenario: No network endpoint is published
- **WHEN** Podman and host listener configuration are inspected
- **THEN** no app-server TCP port is mapped or listening on a host or container network interface

#### Scenario: Unauthorized local user attempts access
- **WHEN** a local process outside the authorized service identity or shared group opens the control socket
- **THEN** operating-system socket permissions deny access

#### Scenario: Stale socket remains after failure
- **WHEN** the prior app-server process is confirmed stopped but its socket path remains
- **THEN** systemd removes the stale socket before container startup and does not remove a socket owned by an active managed process

#### Scenario: Socket file exists before service is ready
- **WHEN** the socket path exists but a 10-second readiness helper cannot complete the Unix WebSocket handshake, protocol initialization, and `account/read`
- **THEN** service readiness remains unhealthy and the exporter reports the Codex source unreachable

### Requirement: Codex owns managed ChatGPT authentication state
The system SHALL enroll a dedicated Habiki ChatGPT managed-login session through the app-server device-code flow and SHALL allow Codex to persist and rotate its OAuth credentials in a protected persistent `CODEX_HOME` state directory.

#### Scenario: Initial device-code enrollment
- **WHEN** no authenticated Codex state exists and an authorized operator runs the enrollment procedure
- **THEN** app-server starts the ChatGPT device-code flow, completes authentication after operator consent, and writes the resulting state only to the protected service state directory

#### Scenario: Credential refresh survives restart
- **WHEN** Codex refreshes or rotates its OAuth credentials and the app-server container subsequently restarts
- **THEN** the restarted service loads the persisted current credential and remains authenticated without copying workstation credentials

#### Scenario: Credential confidentiality
- **WHEN** services, logs, metrics, container configuration, Terraform state, and staged repository files are inspected
- **THEN** no OAuth access token, refresh token, account response, or other sensitive credential material is present

#### Scenario: Static exporter credential is retired
- **WHEN** the app-server migration is complete
- **THEN** the exporter no longer mounts or reads the legacy `codex_oauth_env` age secret

### Requirement: Authentication recovery is explicit and testable
The system SHALL document and validate how Codex managed-login state is recovered after host-state loss, credential expiry, refresh-token reuse, or provider revocation.

#### Scenario: Protected state is recoverable
- **WHEN** an approved encrypted host backup mechanism covers the Codex state directory and a recovery test is performed
- **THEN** the restored app-server loads the protected state without exposing credentials and `account/read` reports an authenticated ChatGPT account

#### Scenario: State cannot be restored
- **WHEN** protected state is unavailable, invalid, revoked, or not covered by an approved backup
- **THEN** the runbook requires a new device-code enrollment and does not reuse the obsolete static bootstrap credential

#### Scenario: Authentication becomes invalid
- **WHEN** app-server reports an expired, reused, revoked, or otherwise invalid refresh token
- **THEN** service health identifies authentication as unavailable and the operational procedure directs an authorized operator to re-enroll the dedicated Habiki session

### Requirement: App-server lifecycle and health are observable
The system SHALL order the AI usage exporter after the app-server workload and SHALL provide enough service and metric health information to distinguish container failure, socket failure, authentication failure, protocol failure, and stale usage data.

#### Scenario: App-server is unavailable at exporter startup
- **WHEN** the exporter starts before the Unix socket is ready
- **THEN** the exporter remains running, reports the Codex source unhealthy, and retries connection without affecting OpenRouter collection

#### Scenario: App-server restarts during operation
- **WHEN** the Podman workload restarts while the exporter is running
- **THEN** the exporter reconnects on a later collection cycle and resumes Codex metrics without requiring its own restart

#### Scenario: Service diagnostics are collected
- **WHEN** an operator investigates a Codex collection failure
- **THEN** systemd and Loki logs identify the failed layer without logging credentials or complete account payloads

#### Scenario: App-server log redaction is verified
- **WHEN** enrollment, account reads, authentication failure, protocol failure, token refresh, and restart paths are exercised with `LOG_FORMAT=json`, warning-level `RUST_LOG`, and debug/trace protocol logging disabled
- **THEN** a fail-closed scan of journald and Loki using ephemeral in-memory secret fingerprints finds no access token, refresh token, authorization header, device code, or complete account response
