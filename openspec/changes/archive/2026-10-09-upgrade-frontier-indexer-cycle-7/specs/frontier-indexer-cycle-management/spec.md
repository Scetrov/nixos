## MODIFIED Requirements

### Requirement: Frontier Indexer cycle configuration
The system SHALL manage Frontier Indexer release image, network and cycle start checkpoint declaratively for Habiki and MUST use the supplied Cycle 7 contracts.

#### Scenario: Cycle 7 image and checkpoint are configured
- **WHEN** Frontier Indexer is enabled on `habiki` for Cycle 7
- **THEN** the deployed container uses `ghcr.io/algo-net/frontier-indexer:v0.4.0` pinned by SHA256 digest and the generated runtime environment includes `SUI_NETWORK=testnet` and `FIRST_CHECKPOINT=387251154`

#### Scenario: Image version is reproducible
- **WHEN** the Frontier Indexer container is deployed
- **THEN** its image reference includes an explicit release tag and cryptographic digest rather than `latest` or a mutable tag alone

#### Scenario: Cycle 7 packages match the declared contracts
- **WHEN** the Cycle 7 image processes world packages on testnet
- **THEN** its configured asset package is `0xc663658ff707985246bc7b5c605a458ec2caea28bfc35c253eb526dcf961643e` and its world package is `0x7be18d6294e533bedd9a5d70a96ce8d9d4b87a7c74188ba65d3fe966bbed9d92`

### Requirement: Disposable indexed data reset
The system SHALL provide an authenticated, writer-safe declarative reset mechanism for disposable Frontier Indexer schema data before starting a new cycle deployment and MUST reject stale or invalid reset markers without destructive action.

#### Scenario: Cycle reset clears the indexer schema once
- **WHEN** Habiki advances the declared reset generation from `6` to `7`
- **THEN** the deployment stops the old indexer writer, authenticates to TimescaleDB, drops and recreates only the configured `indexer` schema before `podman-frontier-indexer.service` starts, and durably records generation `7` after successful reset

#### Scenario: Cycle reset is idempotent after success
- **WHEN** the same reset generation has already been applied
- **THEN** subsequent rebuilds or service restarts do not drop the `indexer` schema again

#### Scenario: Reset does not expose secrets
- **WHEN** the schema reset service runs or fails
- **THEN** database passwords and credential-bearing connection strings are not written to source control, systemd logs, or dashboards

#### Scenario: Stale generation is refused
- **WHEN** the configured reset generation is lower than the valid recorded generation
- **THEN** startup fails without dropping the schema, changing the marker, or starting the stale indexer

#### Scenario: Invalid marker fails closed
- **WHEN** an existing reset marker contains an invalid generation
- **THEN** startup fails without destructive SQL or overwriting the marker

#### Scenario: Missing marker permits initial reset
- **WHEN** a configured reset generation has no existing marker
- **THEN** an authenticated writer-safe reset initializes the schema and records the generation only after success

#### Scenario: Authentication repair precedes destructive reset
- **WHEN** the runtime database secret differs from the existing role password
- **THEN** managed database preflight attempts credential synchronization and validates authentication before reset, and unsuccessful authentication prevents reset and indexer startup

#### Scenario: Reset failure prevents indexing
- **WHEN** schema reset or durable marker publication fails
- **THEN** the indexer does not start and the deployment does not report the reset as successfully applied

#### Scenario: Concurrent startup cannot race resets
- **WHEN** multiple start requests occur during a cycle transition
- **THEN** reset execution is serialized and no indexer writer runs during destructive reset

### Requirement: Cycle upgrade deployment verification
The system SHALL verify a Frontier Indexer cycle upgrade through managed service health, contract configuration, indexed progress, logs, and metrics.

#### Scenario: Upgraded indexer is healthy
- **WHEN** the Cycle 7 deployment completes on `habiki`
- **THEN** TimescaleDB is active, database preflight has succeeded before reset, generation `7` is recorded, migrations have succeeded, and `podman-frontier-indexer.service` is active

#### Scenario: Cycle 7 telemetry is available
- **WHEN** the upgraded indexer is running
- **THEN** Frontier Indexer metrics are available through the managed Prometheus scrape path and recent logs do not show database setup failures

#### Scenario: Cycle 7 indexing advances
- **WHEN** the freshly reset Cycle 7 deployment receives available checkpoints
- **THEN** pipeline progress initializes from `387251154` and advances, with the deployed package configuration matching both supplied Cycle 7 contracts

## ADDED Requirements

### Requirement: Bounded previous-cycle artifact cleanup
The system SHALL inventory and remove confirmed previous-cycle runtime artifacts through targeted automation without preserving a Cycle 6 archive or deleting unrelated infrastructure state.

#### Scenario: Confirmed obsolete artifacts are removed
- **WHEN** inventory identifies Cycle 6-specific caches, dumps or exports owned by this deployment
- **THEN** automation removes only explicitly validated cleanup targets while preserving the database cluster, unrelated schemas, managed secrets and current reset marker

#### Scenario: No extra artifacts exist
- **WHEN** inventory confirms all previous-cycle application state resides in the reset schema and no separate obsolete runtime artifacts exist
- **THEN** schema reset completes cleanup without broad filesystem deletion or global container pruning

#### Scenario: Historical records remain outside cleanup scope
- **WHEN** previous-cycle cleanup runs
- **THEN** Git history, archived OpenSpec artifacts and shared observability history remain untouched

### Requirement: Safe post-transition recovery
The system SHALL treat recovery after Cycle 7 reset as a forward repair that preserves reset generation safety and MUST NOT claim configuration rollback restores discarded Cycle 6 data.

#### Scenario: Operator recovers after cutover failure
- **WHEN** the Cycle 7 indexer fails after a successful generation `7` reset
- **THEN** the documented recovery stops the writer and retains generation `7` and current reset safeguards while repairing or deploying a tested Cycle 7-compatible configuration, rather than activating unsafe pre-transition reset code
