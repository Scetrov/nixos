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

### Requirement: Automatic native OIDC browser entry
Forgejo SHALL automatically initiate its existing Authentik OIDC authorization flow for unauthenticated interactive browser entry through both the Authentik application launch and direct service navigation. The mechanism SHALL preserve native OIDC state/nonce validation and the existing access-group boundary. Existing authenticated Forgejo sessions SHALL open normally without unnecessary reauthentication. Supported local deep links SHALL be restored; unsupported destination forms SHALL fall back safely to the application rather than an external redirect.

#### Scenario: Existing Forgejo session
- **WHEN** a browser with a valid Forgejo session opens the application or a repository deep link
- **THEN** Forgejo serves the authorized destination without starting another OIDC flow

#### Scenario: Authentik session already exists
- **WHEN** an unauthenticated Forgejo browser opens the application directly or from Authentik with an authorized Authentik session
- **THEN** native OIDC completes without another Login with Authentik click

#### Scenario: Authentik session is absent
- **WHEN** an unauthenticated browser opens Forgejo without an Authentik session
- **THEN** it enters Authentik sign-in and returns to Forgejo after successful authorization

#### Scenario: Deep link and unsafe destination
- **WHEN** login begins from a supported local deep link or a request containing an external return destination
- **THEN** the supported local destination is restored after login and the external destination is not followed

### Requirement: Automatic entry has bounded failure and logout behavior
Automatic entry SHALL preserve native callback handling and a usable explicit logout/error landing behavior without redirect loops. Rejected authorization, invalid callback state, session expiry, and provider unavailability SHALL NOT grant access. Administrative recovery SHALL remain documented through a secure host-side procedure without re-enabling normal local-password sign-in.

#### Scenario: Logout
- **WHEN** an authenticated user explicitly signs out of Forgejo
- **THEN** the Forgejo session ends and the logout landing behavior does not immediately force an endless reauthentication cycle

#### Scenario: Authorization or callback fails
- **WHEN** Authentik denies access or native callback validation fails
- **THEN** access remains denied and the browser receives a bounded recoverable failure rather than repeated automatic redirects

#### Scenario: Session expires or identity provider is unavailable
- **WHEN** a session expires or Authentik cannot complete authorization
- **THEN** expired sessions cannot access protected content, normal sign-in can resume after recovery, and the documented secure administrative recovery remains available

### Requirement: Automatic browser entry preserves protocol and deployment boundaries
The change SHALL preserve native Git SSH/HTTPS, API-token, webhook, and health behavior without a blanket Caddy forward-auth gate or browser redirects for machine clients. Automatic entry SHALL be declaratively managed, survive restart/rebuild, preserve private ingress, and keep credentials outside committed plaintext and the Nix store.

#### Scenario: Machine clients remain native
- **WHEN** authorized Git SSH, Git HTTPS, API-token, or webhook clients use existing service endpoints
- **THEN** their native authorization and response behavior remain functional without an interactive Authentik redirect

#### Scenario: Declarative lifecycle
- **WHEN** the targeted Forgejo configuration is redeployed and the service restarts
- **THEN** automatic browser entry remains configured, private access boundaries remain intact, and no secret-bearing configuration is introduced into source or the Nix store
