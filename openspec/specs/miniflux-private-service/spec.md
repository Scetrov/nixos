# miniflux-private-service Specification

## Purpose
Provide a private native Miniflux feed reader on Habiki with operator-only Authentik OIDC, protected shared-database credentials, HTTPS, private observability, automated deployment, and recovery through the Git-managed subscription catalogue or operator-held OPML.

## Requirements

### Requirement: Native private runtime
The system SHALL run Miniflux as a native NixOS systemd service on Habiki, with its application listener bound only to loopback and its public base URL set to `https://feed.net.scetrov.live`. The service MUST NOT start a separate local PostgreSQL instance or run Miniflux in an OCI container.

#### Scenario: Service is enabled
- **WHEN** the Habiki Miniflux configuration is activated
- **THEN** the native Miniflux service runs using a verified, integrity-pinned package and listens only on its configured loopback address
- **AND** no new application port is opened to the network

### Requirement: Dedicated database on the existing PostgreSQL instance
The system SHALL use a dedicated Miniflux database and login role in `authentik-postgresql`. The application role MUST NOT have PostgreSQL superuser, role-creation, or database-creation privileges or access to other applications' private data.

#### Scenario: Database is provisioned for the first time
- **WHEN** Miniflux is deployed without an existing Miniflux database
- **THEN** automation creates its database and restricted role before application migrations and startup
- **AND** Authentik and OpenTofu state databases remain unchanged

#### Scenario: Deployment is repeated or the password is rotated
- **WHEN** provisioning runs against an existing Miniflux database
- **THEN** it preserves subscriptions and application state while reconciling the role credential
- **AND** the service uses the reconciled credential without manual SQL changes

#### Scenario: PostgreSQL is unavailable
- **WHEN** database readiness or reconciliation fails
- **THEN** setup fails with bounded retries and a non-secret diagnostic
- **AND** Miniflux does not start using an unprovisioned database or administrative fallback credentials

### Requirement: HTTPS publication and local name resolution
The system SHALL serve `feed.net.scetrov.live` through Caddy with the existing wildcard certificate and map the name to Habiki through the repository's local networking and DNS patterns. Publication MUST NOT add an external listener beyond the existing HTTPS infrastructure.

#### Scenario: Reader visits the service
- **WHEN** a client resolves and opens `https://feed.net.scetrov.live`
- **THEN** local resolution points to Habiki and Caddy serves valid HTTPS while proxying to the loopback Miniflux listener

### Requirement: Operator-only Authentik OIDC access
The system SHALL provision a native Authentik OIDC application/provider through OpenTofu, restrict application authorization to the designated operator, and configure Miniflux to disable local authentication. The OIDC callback SHALL be strictly registered as `https://feed.net.scetrov.live/oauth2/oidc/callback`.

#### Scenario: Operator signs in for the first time
- **WHEN** the authorized operator completes Authentik OIDC login
- **THEN** Miniflux creates or uses the operator's reader account and permits feed-reader access without local-password bootstrap

#### Scenario: Another Authentik user attempts enrollment
- **WHEN** an authenticated identity outside the operator authorization group attempts OIDC access
- **THEN** Authentik denies application authorization and Miniflux does not enroll that identity through that attempt

#### Scenario: Local login is attempted
- **WHEN** a client attempts to use the local username/password login flow
- **THEN** it cannot establish a reader session through local authentication

### Requirement: Native API compatibility
Caddy SHALL NOT impose blanket interactive forward authentication on Miniflux requests. Miniflux APIs SHALL retain their own authentication and authorization controls without requiring an Authentik browser session.

#### Scenario: Authenticated API client calls Miniflux
- **WHEN** a client sends a valid Miniflux API credential without an Authentik browser session
- **THEN** the request reaches Miniflux and is handled according to its API authorization rules rather than redirected by Caddy to an HTML login

#### Scenario: Unauthenticated API client requests private data
- **WHEN** a client calls a protected API endpoint without valid Miniflux credentials
- **THEN** Miniflux denies access to private reader data

### Requirement: Safe runtime credentials and authoritative OIDC outputs
The system MUST keep database and OIDC secrets out of tracked plaintext, Nix-store configuration, command-line arguments, and logs. Database credentials SHALL originate in Ansible Vault and be delivered through agenix. OpenTofu-managed provider outputs SHALL be authoritative for OIDC consumer credentials and SHALL flow through the existing protected generated-secret workflow.

#### Scenario: Required generated OIDC credentials are invalid
- **WHEN** OIDC consumer values are missing, empty, or placeholders
- **THEN** deployment fails before rendering or activating Miniflux consumer configuration rather than silently reusing stale credentials

#### Scenario: Credentials change
- **WHEN** database or OIDC credentials are rotated through their authoritative automation
- **THEN** runtime secret material and the consuming service are refreshed in the correct order
- **AND** verification reports consistency without printing secret values

### Requirement: Targeted repeatable deployment
The system SHALL provide a targeted Miniflux deployment on Habiki using `./scripts/play.sh --limit habiki --tags miniflux`. All OpenTofu operations MUST use `scripts/tofu.sh`. The workflow SHALL provision identity prerequisites and refresh generated outputs before consumer secret rendering and NixOS activation.

#### Scenario: First targeted deployment
- **WHEN** the documented command runs on an otherwise configured Habiki without Miniflux resources
- **THEN** it provisions the OIDC provider and operator authorization, validates generated credentials, renders secrets, provisions the database, and activates the service without an undocumented second full deployment

#### Scenario: Targeted deployment is repeated
- **WHEN** the same command runs with no intended changes
- **THEN** it preserves the existing reader data and other applications' resources and does not deploy to other hosts

### Requirement: Private observability
The system SHALL send Miniflux service logs to Loki through Alloy, scrape Miniflux metrics privately through Prometheus, and provide sustained service-availability alerting through the existing Grafana observability stack. Caddy MUST deny access to Miniflux metrics through the feed virtual host.

#### Scenario: Monitoring inspects a running service
- **WHEN** monitoring collects Miniflux telemetry
- **THEN** loopback metrics are scrapeable and service logs are identifiable in Loki without intentionally logging credentials or feed contents

#### Scenario: A client requests metrics through Caddy
- **WHEN** a client requests `/metrics` through `feed.net.scetrov.live`
- **THEN** Caddy denies the request without exposing upstream metrics, including when the client has an authenticated reader session

#### Scenario: Service remains unavailable
- **WHEN** the Miniflux scrape stays unavailable beyond the configured alert duration
- **THEN** an actionable service-availability alert is routed through the existing monitoring workflow

### Requirement: Subscription catalogue and OPML disaster recovery
The system SHALL document recovery by reprovisioning Miniflux and its dedicated database, restoring authorized OIDC access, and restoring enabled subscriptions from the Git-managed catalogue through explicitly invoked additive API sync or authenticated import of catalogue-generated/operator-held OPML. API-driven restoration after database loss MUST explicitly require creation of the operator account through OIDC and secure enrollment of a replacement personal API token before reconciliation. The change MUST NOT add PostgreSQL backups, bypass OIDC through local-password/admin or direct SQL account/token bootstrap, or promise recovery of read history, saved articles, preferences, sessions, or API credentials.

#### Scenario: Miniflux state is lost
- **WHEN** the operator reprovisions an empty Miniflux database and imports their existing or catalogue-generated OPML after signing in
- **THEN** feed subscriptions can be restored
- **AND** documentation makes clear that other application state and prior API credentials are not recovered

#### Scenario: Catalogue restores subscriptions through automation
- **WHEN** the operator signs in through authorized OIDC after database loss, creates a new personal API token, stores it securely in Vault, and explicitly runs targeted plan/apply automation
- **THEN** enabled catalogue subscriptions are restored through the native API without local-password/admin bootstrap or direct SQL subscription changes
- **AND** disabled catalogue entries and missing historical application state are not represented as recovered

#### Scenario: Old credentials survive only in Vault
- **WHEN** an API token retained outside the lost database is rejected by the newly provisioned reader
- **THEN** recovery reports the credential bootstrap requirement without creating duplicate users, disabling OIDC, or claiming fully unattended restoration

### Requirement: Non-destructive rollback
The system SHALL document automated removal or disablement of Miniflux-specific runtime, routing, identity, DNS, and monitoring resources. Rollback MUST retain the Miniflux database and role unless the operator explicitly authorizes deletion, and MUST NOT reset schemas to force a package downgrade.

#### Scenario: Operator rolls back the deployment
- **WHEN** Miniflux is removed through the documented automation
- **THEN** no Miniflux route or monitoring target remains dangling
- **AND** Authentik and OpenTofu databases remain intact and Miniflux data is retained by default
