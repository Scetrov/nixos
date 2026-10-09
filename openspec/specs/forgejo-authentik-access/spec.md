# forgejo-authentik-access Specification

## Purpose
TBD - created by archiving change add-private-forgejo. Update Purpose after archive.
## Requirements
### Requirement: Owner-only native OIDC
The system SHALL authenticate normal interactive Forgejo users through native Authentik OIDC using a dedicated provider/application and an access group containing only the confirmed owner initially. Open registration and anonymous repository-content access MUST be disabled; normal users MUST NOT bypass OIDC through local-password sign-in.

#### Scenario: Owner signs in
- **WHEN** the confirmed owner signs in through Authentik
- **THEN** Forgejo creates or associates the intended account and grants its configured access without manual authentication-source setup

#### Scenario: Another Authentik user attempts sign-in
- **WHEN** an Authentik user outside the Forgejo access group attempts OIDC sign-in
- **THEN** access is denied and an authorized Forgejo account is not provisioned for that user

#### Scenario: Anonymous registration or repository access
- **WHEN** an unauthenticated client attempts registration or reads private repository content
- **THEN** registration and repository-content access are denied

#### Scenario: Normal user attempts local-password bypass
- **WHEN** a normal user attempts to bypass Authentik through local-password sign-in
- **THEN** the service does not admit the user through that route

### Requirement: Automated identity reconciliation
The system SHALL manage Authentik provider, application, group membership, and access policy through OpenTofu using `scripts/tofu.sh`. It SHALL idempotently configure Forgejo's native authentication source through supported automation with the matching strict callback URI and validated runtime credentials. Bootstrap administrator credentials, if required, MUST be vault-backed and confined to documented bootstrap/break-glass use.

#### Scenario: First deployment
- **WHEN** Forgejo is deployed with valid prerequisite credentials and a confirmed owner identity
- **THEN** the authentication source and owner administration are established without UI-only configuration or hardcoded passwords

#### Scenario: Identity configuration is reconciled again
- **WHEN** identity automation is rerun or the OIDC client secret rotates
- **THEN** the existing authentication source is reconciled rather than duplicated and subsequent sign-in uses current provider credentials

### Requirement: Native Git credentials remain functional
The system SHALL support Forgejo-authorized Git SSH keys and Git/API tokens independently of interactive browser login, without a blanket Caddy forward-auth gate. It SHALL document account disablement and session/key/token revocation separately from Authentik group removal.

#### Scenario: Token-authenticated Git client
- **WHEN** an authorized Git HTTPS or API client uses a valid Forgejo token
- **THEN** it can perform allowed operations without an interactive Authentik browser redirect

#### Scenario: Owner access is revoked
- **WHEN** the documented access-revocation procedure is executed
- **THEN** it addresses both Authentik sign-in admission and Forgejo account/session/key/token access rather than claiming OIDC group removal alone revokes every issued credential

### Requirement: Sensitive material remains outside source and job environments
The system MUST keep OIDC secrets, service signing secrets, bootstrap credentials, and runner credentials out of committed plaintext, the Nix store, normal command/log output, and CI job environments. Runtime material SHALL be delivered through the protected vault/generated-secret and agenix paths with least-required permissions.

#### Scenario: Runtime secrets are rendered
- **WHEN** deployment renders Forgejo runtime authentication configuration
- **THEN** secrets are loaded from protected runtime files and no secret value appears in committed configuration or normal deployment output
