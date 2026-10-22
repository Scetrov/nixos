## ADDED Requirements

### Requirement: Automatic native OIDC browser entry
Forgejo SHALL automatically initiate its existing Authentik OIDC authorization flow for unauthenticated interactive browser entry through both the Authentik application launch and direct service navigation. The mechanism SHALL be supported by the installed Forgejo release and preserve native OIDC state/nonce validation and the existing access-group boundary. Existing authenticated Forgejo sessions SHALL open normally without unnecessary reauthentication. Supported local deep links SHALL be restored; unsupported destination forms SHALL fall back safely to the application rather than an external redirect.

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
