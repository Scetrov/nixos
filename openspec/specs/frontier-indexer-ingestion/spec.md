# frontier-indexer-ingestion Specification

## Purpose
TBD - created by archiving change fix-frontier-indexer-ingest-concurrency. Update Purpose after archive.
## Requirements
### Requirement: Declarative ingest concurrency on Habiki
The system SHALL declare the Frontier Indexer checkpoint-ingest concurrency declaratively for Habiki, and the deployed runtime environment MUST reflect the declared value.

#### Scenario: Declared concurrency reaches the runtime environment
- **WHEN** `scetrov.services.frontier-indexer.ingestConcurrencyMax` is set to `32` on `habiki` and the deployment is applied
- **THEN** the generated runtime environment file includes `INGEST_CONCURRENCY_MAX=32` and `podman-frontier-indexer.service` is restarted to pick it up

#### Scenario: Unset module default is preserved
- **WHEN** a host enables Frontier Indexer without declaring `ingestConcurrencyMax`
- **THEN** the module default remains `null` and the generated runtime environment omits `INGEST_CONCURRENCY_MAX`, leaving the upstream default in effect

### Requirement: Catch-up throughput must exceed chain production
The configured ingest concurrency SHALL provide sustained checkpoint ingestion throughput that exceeds live Sui testnet chain production so that the indexed chain head does not drift from the live chain head after a backlog is cleared.

#### Scenario: Steady-state ingest exceeds production
- **WHEN** the Frontier Indexer runs with the declared concurrency on Habiki and is not clearing a large backlog
- **THEN** observed ingest rate (checkpoints/second in the `sequential_committer` watermark logs) is consistently above the live chain production rate (~4 cps)

### Requirement: Catch-up must be observable and reversible
The deployment SHALL keep ingest behaviour observable through existing telemetry and SHALL be reversible by lowering the declared concurrency without any database or schema change.

#### Scenario: Throttling is observable
- **WHEN** the public checkpoint store begins returning `429` or triggering the framework's transient retry/backoff path during catch-up
- **THEN** the resulting `429`/retry log lines and a flatlined checkpoint rate are visible in Loki and the indexer does not crash

#### Scenario: Reversible rollback
- **WHEN** `ingestConcurrencyMax` is lowered (for example to `16`) and the targeted deployment re-run
- **THEN** the indexer resumes from its persisted watermark at the lower concurrency, with no database or schema reset performed
