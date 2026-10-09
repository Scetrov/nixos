## MODIFIED Requirements

### Requirement: Generated OIDC outputs are authoritative
The deployment system SHALL treat OpenTofu-managed Authentik OAuth2 provider outputs as the authoritative source for Grafana, Dependency Track, and Forgejo OIDC client IDs and client secrets.

#### Scenario: Generated secrets are refreshed from OpenTofu
- **WHEN** Authentik OIDC providers are created or updated through the OpenTofu workflow
- **THEN** the deployment system writes the resulting Grafana, Dependency Track, and Forgejo OIDC client IDs and client secrets into `src/generated-secrets.yml`

#### Scenario: Service deployment consumes generated values
- **WHEN** the secrets and NixOS deployment phases render Grafana, Dependency Track, or Forgejo runtime configuration
- **THEN** they use the OIDC values from `src/generated-secrets.yml` rather than placeholders, defaults, or previously deployed runtime values

### Requirement: Placeholder OIDC values are rejected
The deployment system MUST fail before rendering or deploying service configuration when required Grafana, Dependency Track, or Forgejo OIDC generated-secret values are empty, missing, malformed, or equal to placeholder values.

#### Scenario: Dependency Track placeholder is present
- **WHEN** `dtrack_oidc_client_id` resolves to `dtrack_oidc_client_id_placeholder`
- **THEN** the deployment fails before generating `/root/secrets/dtrack_oidc_client_id.age` or rebuilding Dependency Track service configuration

#### Scenario: Grafana client ID is missing
- **WHEN** `grafana_authentik_client_id` is undefined or empty
- **THEN** the deployment fails before generating `/root/secrets/grafana_authentik_client_id.age` or rebuilding Grafana service configuration

#### Scenario: Forgejo generated credentials are invalid
- **WHEN** required Forgejo OIDC generated credentials are missing, empty, malformed, or placeholders
- **THEN** deployment fails before rendering Forgejo consumer secrets or reconciling its authentication source and does not silently reuse stale deployed credentials

### Requirement: Generated-secret refresh precedes service configuration
The deployment workflow SHALL ensure generated OIDC secrets are available before agenix secret files and NixOS service configuration for Grafana, Dependency Track, and Forgejo are rendered.

#### Scenario: Single command deployment requires generated outputs
- **WHEN** an operator runs the documented targeted deployment for Habiki OIDC-enabled services
- **THEN** the workflow refreshes or validates OpenTofu-generated OIDC outputs before running the secrets and NixOS roles that consume them

#### Scenario: Generated outputs change
- **WHEN** OpenTofu changes a Grafana, Dependency Track, or Forgejo OIDC client ID or client secret
- **THEN** the following service deployment uses the new generated-secret values without requiring an undocumented second full deploy

#### Scenario: Forgejo is deployed for the first time
- **WHEN** the targeted Forgejo deployment starts without an existing Forgejo provider
- **THEN** it provisions the Authentik prerequisites through the secure OpenTofu wrapper before validating and configuring Forgejo consumers

### Requirement: OIDC consistency can be verified safely
The deployment system SHALL provide verification steps that confirm service-facing OIDC client IDs match Authentik provider client IDs without exposing secret values.

#### Scenario: Grafana client ID verification
- **WHEN** verification compares the Grafana OAuth redirect client ID with the Authentik Grafana provider client ID
- **THEN** it reports only non-sensitive metadata such as match status, length, or redacted fingerprint

#### Scenario: Dependency Track client ID verification
- **WHEN** verification inspects Dependency Track frontend OIDC configuration
- **THEN** it confirms the client ID is non-placeholder and matches the Authentik Dependency Track provider without printing the raw client secret

#### Scenario: Forgejo client ID verification
- **WHEN** verification compares Forgejo's authentication-source client ID with its Authentik provider
- **THEN** it confirms a non-placeholder match using non-sensitive metadata without printing the client secret
