## MODIFIED Requirements

### Requirement: Frontier Indexer database startup remediation
The system SHALL ensure Frontier Indexer validates its database connection, optional schema reset prerequisites, and setup prerequisites before starting the indexer container, without exposing database credentials in logs or source control.

#### Scenario: Database connection is validated before indexer start
- **WHEN** Frontier Indexer is enabled on `habiki`
- **THEN** the startup sequence validates the TimescaleDB host, port, database, user, password source, and required connection path before `podman-frontier-indexer.service` starts

#### Scenario: Database preflight failure is actionable
- **WHEN** the database preflight cannot connect or validate setup prerequisites
- **THEN** the failing systemd unit exits before starting the indexer container and logs a clear non-secret diagnostic identifying the failed prerequisite

#### Scenario: Schema reset completes before indexer start
- **WHEN** Frontier Indexer declares a schema reset generation for a cycle upgrade
- **THEN** the startup sequence completes the reset successfully before `podman-frontier-indexer.service` starts, or fails with a clear non-secret diagnostic before starting the indexer container

#### Scenario: Secrets are not exposed
- **WHEN** Frontier Indexer database checks or schema reset steps run or fail
- **THEN** database passwords and connection strings containing credentials are not written to Nix files, OpenTofu files, systemd logs, or Grafana dashboards

#### Scenario: Indexer remains running after remediation
- **WHEN** the remediation is deployed and TimescaleDB is healthy
- **THEN** `podman-frontier-indexer.service` remains active and no longer logs `Failed to get connection for database setup` during normal startup
