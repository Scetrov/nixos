## ADDED Requirements

### Requirement: Declarative Home Assistant Prometheus Export
The system SHALL manage Home Assistant's internal Prometheus integration declaratively in the generated `configuration.yaml` and SHALL limit initial export scope to approved environmental entities.

#### Scenario: Prometheus integration is enabled declaratively
- **WHEN** the Home Assistant module is enabled on `habiki`
- **THEN** the generated `/var/lib/homeassistant/configuration.yaml` includes a managed `prometheus` configuration for Home Assistant's internal metrics endpoint

#### Scenario: Export scope is curated
- **WHEN** the managed Prometheus integration is rendered
- **THEN** it includes the approved environmental entities needed for dashboards, including supported temperature, humidity, CO2, PM2.5, PM10, and air-quality sensors, and excludes unrelated diagnostic, firmware, and Bluetooth signal entities from the initial export set

### Requirement: Local Prometheus Scrape Authentication
The system SHALL scrape Home Assistant metrics locally from Prometheus using an age-backed Home Assistant access token rather than exposing an unauthenticated public metrics path.

#### Scenario: Prometheus scrapes Home Assistant locally
- **WHEN** observability configuration is applied on `habiki`
- **THEN** Prometheus declares a Home Assistant scrape job that targets the local Home Assistant listener, uses Home Assistant's Prometheus metrics path, and attaches stable labels for at least `service=home-assistant`

#### Scenario: Scrape authentication is secret-backed
- **WHEN** the Home Assistant scrape job is configured
- **THEN** the authorization credential is sourced from a repo-managed age secret file and is not hardcoded into the NixOS module, Home Assistant configuration, or dashboard definitions

### Requirement: Environmental Metrics Validation
The system SHALL verify that Home Assistant environmental metrics flow through the existing Prometheus and Mimir path after deployment.

#### Scenario: Metrics are queryable after rollout
- **WHEN** the Home Assistant Prometheus integration and scrape job are deployed
- **THEN** validation confirms that the Home Assistant target is up in Prometheus and that exported environmental metrics are queryable through both the local Prometheus instance and the Mimir-backed Grafana datasource path
