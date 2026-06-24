## ADDED Requirements

### Requirement: Prioritized Grafana error findings
The system SHALL provide a repeatable investigation workflow that groups Grafana/Loki error and warning findings, ranks them by severity and frequency, and identifies which findings require implementation work.

#### Scenario: Error findings are grouped
- **WHEN** an operator investigates Grafana/Loki logs for a selected time range
- **THEN** recurring messages are grouped by similar source and message rather than presented only as raw log lines

#### Scenario: Service failures outrank benign noise
- **WHEN** grouped findings include both service crash loops and non-fatal warning noise
- **THEN** findings that indicate failed services or unavailable dependencies are ranked above correctable hardware messages or known benign warnings

#### Scenario: Low-priority findings are documented
- **WHEN** a finding is deferred because it is low severity or likely environmental noise
- **THEN** the investigation records the reason it is deferred and the condition that would make it actionable

### Requirement: Frontier Indexer database startup remediation
The system SHALL ensure Frontier Indexer validates its database connection and setup prerequisites before starting the indexer container, without exposing database credentials in logs or source control.

#### Scenario: Database connection is validated before indexer start
- **WHEN** Frontier Indexer is enabled on `habiki`
- **THEN** the startup sequence validates the TimescaleDB host, port, database, user, password source, and required connection path before `podman-frontier-indexer.service` starts

#### Scenario: Database preflight failure is actionable
- **WHEN** the database preflight cannot connect or validate setup prerequisites
- **THEN** the failing systemd unit exits before starting the indexer container and logs a clear non-secret diagnostic identifying the failed prerequisite

#### Scenario: Secrets are not exposed
- **WHEN** Frontier Indexer database checks run or fail
- **THEN** database passwords and connection strings containing credentials are not written to Nix files, OpenTofu files, systemd logs, or Grafana dashboards

#### Scenario: Indexer remains running after remediation
- **WHEN** the remediation is deployed and TimescaleDB is healthy
- **THEN** `podman-frontier-indexer.service` remains active and no longer logs `Failed to get connection for database setup` during normal startup

### Requirement: Post-remediation verification
The system SHALL include verification steps for each implemented remediation so operators can confirm the finding is resolved or explicitly accepted.

#### Scenario: Frontier Indexer verification covers service and telemetry
- **WHEN** Frontier Indexer remediation is deployed
- **THEN** verification confirms systemd service health, absence of the database setup failure in recent logs, and availability of Frontier Indexer metrics through the managed Prometheus/Mimir path

#### Scenario: PCIe AER verification records mitigation decision
- **WHEN** the PCIe AER finding is investigated
- **THEN** verification records the affected host and device mapping, the selected decision, and whether recent logs still contain high-volume AER correctable events

#### Scenario: Grafana warning verification records fix or acceptance
- **WHEN** the Grafana resource-client warning is investigated
- **THEN** verification records whether the warning was fixed by configuration/update or accepted as benign noise with an explicit rationale

### Requirement: Safe handling of PCIe AER noise
The system SHALL handle PCIe AER correctable error spam with a host-specific, reversible decision rather than an undocumented fleet-wide suppression.

#### Scenario: PCIe source is identified before mitigation
- **WHEN** PCIe AER mitigation is considered
- **THEN** the implementation identifies the emitting host, PCI address, likely device, and relevant kernel or firmware context before changing boot parameters

#### Scenario: Suppression is scoped and reversible
- **WHEN** a boot-parameter mitigation is applied for PCIe AER noise
- **THEN** it is scoped to the affected host configuration and includes a documented rollback path

### Requirement: Grafana resource-client warning triage
The system SHALL triage Grafana `resource-client-auth-interceptor` warnings before filtering or suppressing them.

#### Scenario: Grafana warning source is investigated
- **WHEN** Grafana emits repeated `calling resource store as the service without id token` warnings
- **THEN** the implementation checks deployed Grafana version, configured plugins/features, and relevant service account usage before deciding on remediation

#### Scenario: Benign warning acceptance is explicit
- **WHEN** the Grafana warning is determined to be benign or upstream-noise
- **THEN** the repository records the acceptance rationale and any log filtering or dashboard treatment remains declaratively managed
