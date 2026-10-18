# Shared PostgreSQL TLS Specification

## Purpose

Protect all TCP access to Habiki's shared PostgreSQL instance with verified native TLS, restricted ACME certificate delivery and non-destructive automated operations while retaining local administrative recovery.

## Requirements

### Requirement: Verified TLS for shared PostgreSQL

Habiki's existing `authentik-postgresql` instance SHALL serve native TLS on its existing ports using the ACME `scetrov.live` certificate covering `*.net.scetrov.live`. Every production TCP consumer SHALL verify the certificate chain and hostname using `verify-full` or equivalent, without plaintext or verification-bypass fallback. After cutover, PostgreSQL SHALL reject plaintext TCP, including loopback and container-network connections, while preserving restricted local Unix-socket administration.

#### Scenario: Clients connect after cutover
- **WHEN** Authentik server/worker, Miniflux, OpenTofu or maintenance tooling connects over TCP
- **THEN** the connection uses verified TLS and existing application/database behaviour is preserved
- **AND** OpenTofu access remains behind `scripts/tofu.sh`

#### Scenario: An insecure connection is attempted
- **WHEN** a client attempts plaintext TCP or cannot verify the server's certificate chain, validity or hostname
- **THEN** the connection fails without falling back to an insecure connection

#### Scenario: Local recovery is needed
- **WHEN** an authorized operator uses the restricted administrative Unix socket
- **THEN** database administration remains available independently of network TLS

### Requirement: Protected certificate delivery and renewal

Existing ACME/systemd automation SHALL supply the certificate chain and key through a restricted PostgreSQL-specific directory mounted read-only into the container. Permissions SHALL satisfy PostgreSQL's requirements and the actual container identity. Private keys MUST NOT enter Git, the Nix store, logs or command-line values; ACME account material and DNS credentials MUST NOT be exposed to the container.

Certificate preparation SHALL precede database startup without making ACME issuance depend on the database or Authentik. Renewal SHALL validate the replacement pair before publication and reload PostgreSQL without restarting it or disrupting existing Caddy certificate consumers. Failures SHALL be reported through existing service logging without disabling TLS or verification. Invalid replacement material MUST NOT overwrite the working pair.

#### Scenario: A certificate renews
- **WHEN** ACME supplies a valid replacement certificate and matching key
- **THEN** automation installs the protected pair and reloads PostgreSQL without a database restart

#### Scenario: Certificate preparation fails
- **WHEN** replacement material is invalid or cannot be prepared
- **THEN** automation reports failure and leaves the working pair in place

#### Scenario: Habiki starts
- **WHEN** the host starts with its provisioned ACME certificate
- **THEN** readable protected certificate material is prepared before PostgreSQL starts

### Requirement: Non-destructive automated cutover

The migration SHALL inventory this instance's TCP consumers and use existing targeted Ansible/NixOS and encrypted-secret workflows. Enable TLS before migrating clients, and reject plaintext only after verified client access is established. Temporary mixed-mode access SHALL be limited to the planned cutover. Existing data, roles, credentials, volumes and restricted socket access SHALL be preserved; other PostgreSQL instances SHALL remain unchanged.

Completion SHALL include focused regression tests and operator verification of real clients, plaintext rejection, certificate-verification failures and renewal. Startup ordering SHALL be checked, with reboot verification coordinated with the operator. A short runbook SHALL describe endpoints, trust settings and non-destructive local recovery. Reopening plaintext requires an explicit operator decision, not automatic rollback.

#### Scenario: The populated instance is migrated
- **WHEN** operators apply the targeted cutover
- **THEN** all TCP consumers use verified TLS, plaintext is rejected and application health is confirmed without database reinitialization or manual plaintext secret edits

#### Scenario: Renewal is verified
- **WHEN** operators exercise certificate renewal
- **THEN** a fresh connection serves the replacement certificate without restarting PostgreSQL

#### Scenario: Local OpenTofu checks run
- **WHEN** supported credential-free wrapper checks run
- **THEN** they do not load production credentials or connect to the production database
