# immich-secure-access Specification

## Purpose

Provide HTTPS-only Immich access through Caddy with native Authentik OIDC,
protected runtime credentials, compatible browser/mobile/API protocols and
storage-preserving local administrator recovery.

## Requirements
### Requirement: HTTPS proxy is the application ingress

Immich SHALL be served at `https://immich.net.scetrov.live` by Caddy using existing certificate automation. Its application listener SHALL bind to loopback with automatic firewall opening disabled, and port 3000 MUST NOT be directly reachable from other hosts.

#### Scenario: HTTPS application access
- **WHEN** a client opens the configured HTTPS hostname
- **THEN** Caddy presents a valid certificate and proxies the original application routes to Immich on loopback

#### Scenario: Direct listener access is blocked
- **WHEN** another host attempts to connect directly to Habiki on port 3000
- **THEN** it cannot reach Immich

### Requirement: Native Authentik login supports intended clients

Immich SHALL use a declaratively managed Authentik OIDC provider/application with explicit redirect URIs verified for the deployed version's web and supported mobile flows. Access SHALL follow the repository's intended-user authorization policy. Caddy MUST NOT impose a second forward-auth login gate on Immich.

#### Scenario: Authorized browser login
- **WHEN** an authorized user selects Authentik sign-in and completes authentication
- **THEN** Immich establishes a working application session and can provision the new account without migrating an existing user

#### Scenario: Unauthorized user
- **WHEN** a user outside the intended Authentik access policy attempts OIDC sign-in
- **THEN** Authentik refuses application authorization

#### Scenario: Mobile backup
- **WHEN** an authorized user signs in from a supported Immich mobile app
- **THEN** the callback completes and photo backup/background synchronization works through the HTTPS endpoint

### Requirement: Credentials remain outside declarative store content

OIDC credentials SHALL be provisioned through existing secure OpenTofu and Ansible/agenix automation and consumed through a restricted runtime configuration or secret-file facility. Client secrets MUST NOT appear in committed plaintext, Nix store configuration, command arguments or logs. Deployment MUST reject missing or placeholder credentials before configuring Immich and MUST use credentials matching the Authentik provider.

#### Scenario: Credential deployment
- **WHEN** the provider and Immich configuration are deployed
- **THEN** the runtime consumer receives matching provider credentials through protected files and verification does not print secret values

#### Scenario: Required credentials are unavailable
- **WHEN** required provider credentials are missing or placeholders
- **THEN** deployment fails before configuring Immich with invalid credentials

### Requirement: Application protocols remain functional

The HTTPS endpoint SHALL support native API-key access, media upload/download and realtime connections without an additional proxy login. The configuration SHALL remain functional after a service restart or host configuration rebuild.

#### Scenario: API and media access
- **WHEN** an authorized client uses its native API key to upload and retrieve media, including a representative large upload
- **THEN** Immich processes the requests through Caddy without an Authentik HTML login response or proxy-induced upload failure

#### Scenario: Realtime and restart
- **WHEN** an authenticated client uses supported realtime functionality and reconnects after an Immich restart or rebuild
- **THEN** the connection works through the same HTTPS endpoint with OIDC configuration intact

### Requirement: Recovery requires neither OIDC nor destructive migration

Local administrator login SHALL remain available as a documented, tested recovery path when Authentik is unavailable. Deployment and rollback SHALL preserve database/media storage and SHALL NOT introduce user migration or storage reset. Configuration changes SHALL use existing automation with targeted Habiki deployment instructions, and relevant service errors SHALL remain available through existing Grafana log collection.

#### Scenario: Identity provider outage
- **WHEN** Authentik is unavailable
- **THEN** an administrator can use the documented local recovery login through HTTPS without reopening port 3000

#### Scenario: Rollback
- **WHEN** the operator rolls back the OIDC integration through documented automation
- **THEN** storage remains intact and administrator access remains possible through Caddy without direct application-port exposure

#### Scenario: Operational verification
- **WHEN** an operator follows the deployment and troubleshooting documentation
- **THEN** it identifies the targeted commands, recovery procedure, verification checks and existing Grafana log path without exposing credentials
