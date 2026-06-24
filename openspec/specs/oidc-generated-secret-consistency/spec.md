# oidc-generated-secret-consistency Specification

## Purpose

Ensure OpenTofu-generated OIDC client IDs and client secrets are treated as authoritative deployment inputs for OIDC-enabled services, with safe validation and verification that prevents placeholder or stale values from reaching runtime configuration.

## Requirements

### Requirement: Generated OIDC outputs are authoritative
The deployment system SHALL treat OpenTofu-managed Authentik OAuth2 provider outputs as the authoritative source for Grafana and Dependency Track OIDC client IDs and client secrets.

#### Scenario: Generated secrets are refreshed from OpenTofu
- **WHEN** Authentik OIDC providers are created or updated through the OpenTofu workflow
- **THEN** the deployment system writes the resulting Grafana and Dependency Track OIDC client IDs and client secrets into `src/generated-secrets.yml`

#### Scenario: Service deployment consumes generated values
- **WHEN** the secrets and NixOS deployment phases render Grafana or Dependency Track runtime configuration
- **THEN** they use the OIDC values from `src/generated-secrets.yml` rather than placeholders, defaults, or previously deployed runtime values

### Requirement: Placeholder OIDC values are rejected
The deployment system MUST fail before rendering or deploying service configuration when required Grafana or Dependency Track OIDC generated-secret values are empty, missing, malformed, or equal to placeholder values.

#### Scenario: Dependency Track placeholder is present
- **WHEN** `dtrack_oidc_client_id` resolves to `dtrack_oidc_client_id_placeholder`
- **THEN** the deployment fails before generating `/root/secrets/dtrack_oidc_client_id.age` or rebuilding Dependency Track service configuration

#### Scenario: Grafana client ID is missing
- **WHEN** `grafana_authentik_client_id` is undefined or empty
- **THEN** the deployment fails before generating `/root/secrets/grafana_authentik_client_id.age` or rebuilding Grafana service configuration

### Requirement: Generated-secret refresh precedes service configuration
The deployment workflow SHALL ensure generated OIDC secrets are available before agenix secret files and NixOS service configuration for Grafana and Dependency Track are rendered.

#### Scenario: Single command deployment requires generated outputs
- **WHEN** an operator runs the documented targeted deployment for Habiki OIDC-enabled services
- **THEN** the workflow refreshes or validates OpenTofu-generated OIDC outputs before running the secrets and NixOS roles that consume them

#### Scenario: Generated outputs change
- **WHEN** OpenTofu changes a Grafana or Dependency Track OIDC client ID or client secret
- **THEN** the following service deployment uses the new generated-secret values without requiring an undocumented second full deploy

### Requirement: OIDC consistency can be verified safely
The deployment system SHALL provide verification steps that confirm service-facing OIDC client IDs match Authentik provider client IDs without exposing secret values.

#### Scenario: Grafana client ID verification
- **WHEN** verification compares the Grafana OAuth redirect client ID with the Authentik Grafana provider client ID
- **THEN** it reports only non-sensitive metadata such as match status, length, or redacted fingerprint

#### Scenario: Dependency Track client ID verification
- **WHEN** verification inspects Dependency Track frontend OIDC configuration
- **THEN** it confirms the client ID is non-placeholder and matches the Authentik Dependency Track provider without printing the raw client secret
