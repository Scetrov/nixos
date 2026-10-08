## ADDED Requirements

### Requirement: Centralized service logs
The system SHALL deliver Forgejo logs to Loki through existing collection infrastructure with stable service-identifying labels and without authentication secrets.

#### Scenario: Service event is emitted
- **WHEN** Forgejo emits a startup or failure event
- **THEN** the event is discoverable in Loki under its corresponding service identity

### Requirement: Private health and metrics collection
The system SHALL collect Forgejo metrics and service-health signals through private endpoints or existing host telemetry. Metrics credentials SHALL use protected runtime secrets when required, and internal metrics MUST NOT be exposed through the Forgejo HTTPS site.

#### Scenario: Prometheus scrapes Forgejo
- **WHEN** Prometheus performs its configured scrape
- **THEN** it obtains Forgejo metrics through the private configured path without exposing credentials

#### Scenario: Client requests internal metrics
- **WHEN** a normal client requests an internal metrics endpoint through the Forgejo site
- **THEN** it is not provided access to the internal listener

### Requirement: Actionable Grafana health visibility
The system SHALL provide declaratively managed Grafana visibility and health alerting for Forgejo availability using observed metrics/log fields and service-health signals. Dashboard colors SHALL follow the repository palette. Runner and job observability are outside this change's scope.

#### Scenario: Forgejo becomes unavailable
- **WHEN** Forgejo availability remains unhealthy beyond the configured alert threshold
- **THEN** Grafana health visibility and alerting identify the Forgejo service issue
