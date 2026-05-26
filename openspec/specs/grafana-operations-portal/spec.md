# grafana-operations-portal Specification

## Purpose

TBD - created by archiving change grafana-single-pane-of-glass. Update Purpose after archive.
## Requirements
### Requirement: Grafana provides an operator landing experience

The system SHALL make Grafana the primary operations entrypoint by exposing platform-wide overview dashboards and a service catalog for the managed environment.

#### Scenario: Platform overview is available

- **WHEN** an operator opens the Grafana portal
- **THEN** Grafana presents a platform-wide overview that summarizes host health and observability stack health using the configured Grafana datasources

#### Scenario: Service catalog is available

- **WHEN** an operator needs to inspect an application or infrastructure component
- **THEN** Grafana provides a service catalog or equivalent dashboard index with entries for the managed services and links to their detailed views

### Requirement: Service dashboards support cross-signal drilldown

The system SHALL provide per-service dashboards that let operators navigate from high-level status into metrics, logs, traces, profiles, incidents, and related operational views when those signals exist.

#### Scenario: Cross-signal navigation is available

- **WHEN** an operator selects a service from the platform overview or service catalog
- **THEN** the service dashboard provides drilldowns into the relevant metrics, logs, traces, and profile views using the selected service context

#### Scenario: Partial signal coverage is handled explicitly

- **WHEN** a service does not yet emit one or more advanced signals such as traces or profiles
- **THEN** the service dashboard still provides the available signals and clearly indicates which signal types are not yet available

### Requirement: Managed services meet a minimum observability contract

The system SHALL onboard managed services into Grafana using a common service identity so signals can be correlated across metrics, logs, and traces.

#### Scenario: Signals share service identity

- **WHEN** a managed service emits telemetry into the observability stack
- **THEN** that telemetry includes stable identifiers for at least the service name and host so Grafana can correlate signals across backends

#### Scenario: Service onboarding includes a baseline

- **WHEN** a managed service is added to the Grafana operations portal
- **THEN** it exposes at least one supported operational signal and a defined path for adding the remaining supported signals over time

### Requirement: Dashboard catalog is declaratively managed

The system SHALL manage the operations overview, service catalog, and per-service dashboards from source control using the repository's declarative Grafana workflows.

#### Scenario: Dashboard definitions remain in source control

- **WHEN** observability dashboards are added or updated
- **THEN** their definitions are stored in the repository and applied through the established deployment workflows rather than manual-only Grafana UI edits

#### Scenario: Dashboard organization is stable

- **WHEN** Grafana provisions the dashboard catalog
- **THEN** dashboards are grouped into a stable structure that separates platform-wide views from service-specific views

### Requirement: Home Assistant service dashboard shows live metrics coverage
The system SHALL provide a Home Assistant service dashboard that shows live operational metrics coverage once Home Assistant metrics are onboarded.

#### Scenario: Service dashboard shows scrape health
- **WHEN** an operator opens the Home Assistant service dashboard after metrics onboarding
- **THEN** the dashboard shows Home Assistant scrape health and related operational metrics from the Prometheus and Mimir datasources alongside the existing log view

#### Scenario: Metrics placeholder is removed
- **WHEN** the Home Assistant dashboard definitions are updated for this change
- **THEN** the previous placeholder stating that Home Assistant metrics are not yet enabled is replaced with panels backed by the active telemetry path

### Requirement: Home Assistant environmental telemetry dashboard is available
The system SHALL provide a declaratively managed Grafana dashboard for Home Assistant environmental telemetry so operators can inspect indoor climate and air-quality history.

#### Scenario: Environmental dashboard includes numeric air-quality metrics
- **WHEN** an operator opens the Home Assistant environmental dashboard
- **THEN** the dashboard includes time-series views for the onboarded CO2, PM2.5, and PM10 metrics using the retained metrics datasource path

#### Scenario: Environmental dashboard includes climate metrics
- **WHEN** an operator opens the Home Assistant environmental dashboard
- **THEN** the dashboard includes temperature and humidity panels for the approved Home Assistant entities exported through the managed Prometheus integration
