## ADDED Requirements

### Requirement: Frontier Indexer cycle configuration
The system SHALL manage Frontier Indexer release image and cycle start checkpoint declaratively for Habiki.

#### Scenario: Cycle 6 image and checkpoint are configured
- **WHEN** Frontier Indexer is enabled on `habiki` for cycle 6
- **THEN** the deployed indexer container uses `ghcr.io/ocky-public/frontier-indexer:v0.3.7` and the generated runtime environment includes `FIRST_CHECKPOINT=352596413`

#### Scenario: Image version is reproducible
- **WHEN** the Frontier Indexer container is deployed
- **THEN** the image reference is pinned to an explicit version tag rather than `latest`

### Requirement: Disposable indexed data reset
The system SHALL provide a declarative reset mechanism for disposable Frontier Indexer schema data before starting a new cycle deployment.

#### Scenario: Cycle reset clears the indexer schema once
- **WHEN** Habiki declares a new Frontier Indexer schema reset generation for cycle 6
- **THEN** the deployment drops and recreates the configured `indexer` schema before `podman-frontier-indexer.service` starts and records that the generation has been applied

#### Scenario: Cycle reset is idempotent after success
- **WHEN** the same reset generation has already been applied
- **THEN** subsequent rebuilds or service restarts do not drop the `indexer` schema again

#### Scenario: Reset does not expose secrets
- **WHEN** the schema reset service runs or fails
- **THEN** database passwords and credential-bearing connection strings are not written to source control, systemd logs, or dashboards

### Requirement: Cycle upgrade deployment verification
The system SHALL verify a Frontier Indexer cycle upgrade through managed service health, logs, and metrics.

#### Scenario: Upgraded indexer is healthy
- **WHEN** the cycle 6 deployment completes on `habiki`
- **THEN** TimescaleDB is active, the schema reset service has completed for the declared generation, database preflight has succeeded, and `podman-frontier-indexer.service` is active

#### Scenario: Cycle 6 telemetry is available
- **WHEN** the upgraded indexer is running
- **THEN** Frontier Indexer metrics are available through the managed Prometheus scrape path and recent logs do not show database setup failures
