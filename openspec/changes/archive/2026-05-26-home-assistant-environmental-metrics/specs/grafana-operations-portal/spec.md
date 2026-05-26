## ADDED Requirements

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
