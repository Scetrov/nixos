## Context

Habiki manages Frontier Indexer declaratively through `src/roles/nixos/files/etc/nixos/modules/frontier-indexer.nix` and enables it in `src/roles/nixos/files/device-configuration/habiki.nix`. The module provisions a dedicated Podman network, a TimescaleDB container, a generated non-world-readable indexer environment file, a database readiness check, an authenticated preflight, the indexer container, and Prometheus scrape configuration.

The current Habiki deployment starts from checkpoint `302790346` and the module default image is `ghcr.io/ocky-public/frontier-indexer:v0.3.5`. Frontier Indexer `0.3.7` is the cycle 6 release and upstream recommends starting from checkpoint `352596413`. The user explicitly allows discarding old cycle 5 data, so the design does not need to preserve or rename the existing `indexer` schema.

The deployment must continue to follow repository standards: automation first, no secret hardcoding, targeted deployment with `./scripts/play.sh --limit habiki --tags frontier-indexer`, and operational verification through systemd/Podman/Grafana signals.

## Goals / Non-Goals

**Goals:**

- Deploy Frontier Indexer `0.3.7` to Habiki.
- Start cycle 6 indexing from `FIRST_CHECKPOINT=352596413`.
- Discard old indexed data in the existing `indexer` schema through an automated and repeatable mechanism.
- Keep database credentials sourced from age/Ansible-managed secrets and runtime environment generation.
- Preserve the existing database preflight so startup failures are caught before the indexer container runs.
- Keep Prometheus/Grafana observability intact and verify the upgraded service after deployment.

**Non-Goals:**

- Preserve or archive cycle 5 indexed data.
- Introduce a new database host, database name, or credential source.
- Add external pipelines or transports such as Redis, NATS, AMQP, or Socket.IO.
- Redesign Frontier Indexer dashboards beyond verification that existing signals still work.
- Imperatively hot-patch Habiki outside the NixOS/Ansible deployment flow, except for read-only investigation and verification.

## Decisions

### Decision: Use a declarative schema reset instead of manual database mutation

Add a module-level reset mechanism that runs before `podman-frontier-indexer.service` and after TimescaleDB connectivity has been validated enough to safely execute SQL. The reset should drop and recreate only the configured `DB_SCHEMA` (`indexer`), not the whole database cluster.

A generation-style option is preferred over a bare boolean, for example `resetSchemaGeneration = null | int`. Habiki can set the value to `6` for the cycle 6 reset. The generated reset service can record the applied generation in state, such as `/var/lib/frontier-indexer/schema-reset-generation`, so the reset is idempotent and does not erase data on every rebuild or service restart.

Alternatives considered:

- Manual `psql DROP SCHEMA`: rejected because it bypasses the automation-first standard and is hard to reproduce during BCDR.
- Wipe `/var/lib/frontier-indexer/timescaledb-data`: rejected because it is broader than required and risks removing unrelated PostgreSQL cluster state.
- Rename `indexer` to `cycle_5`: rejected because old data is explicitly disposable and preserving it adds unnecessary state.

### Decision: Keep schema name `indexer`

Continue using `DB_SCHEMA=indexer` and reset its contents rather than switching cycle 6 to a different schema name. This keeps dashboards, downstream queries, and operator expectations stable.

Alternatives considered:

- Use `DB_SCHEMA=cycle_6`: rejected because it would require consumers to know about the new schema and leaves the old schema dangling.
- Rename cycle 5 schema and let the container recreate `indexer`: possible, but unnecessary because preservation is not required.

### Decision: Rely on default all-pipeline behavior unless `PIPELINES` is explicitly introduced later

The current deployment does not mount a `pipelines.toml` and does not set `PIPELINES`. Frontier Indexer documentation states that when `PIPELINES` is unset, all pipelines run. Therefore the cycle 6 upgrade should not add a pipelines file unless implementation discovers the container image now requires one.

Alternatives considered:

- Add and mount `pipelines.toml`: rejected for now because it creates another artifact to maintain and risks accidentally omitting future pipelines.
- Set `PIPELINES` explicitly: rejected for now because all-pipeline default is safer for a full indexer deployment.

### Decision: Prefer Habiki-specific image and checkpoint settings while retaining sane module defaults

Set Habiki to the cycle 6 image/checkpoint explicitly, or update the module default image if there is only one intended Frontier Indexer version in the fleet. The implementation should avoid hiding the image bump inside an imperative deployment command.

Alternatives considered:

- Pull `latest`: rejected because it weakens reproducibility and rollback clarity.
- Runtime-only `podman pull/run`: rejected because it bypasses NixOS declarative state.

## Risks / Trade-offs

- **Accidental repeated data loss** → Use a generation marker file so the schema reset runs once per declared generation, not every restart.
- **Reset targets the wrong schema** → Source the schema from the generated runtime env file and validate it is non-empty and expected before executing SQL.
- **Indexer starts before reset completes** → Add systemd ordering so reset is required by and before `podman-frontier-indexer.service`.
- **Preflight passes but migrations fail after schema reset** → Verify logs after startup and keep the existing database setup failure dashboard signal visible.
- **Upstream pipeline behavior changed** → Inspect `0.3.7` docs/image logs during implementation; if `pipelines.toml` is required, add a declarative config file and mount it.
- **Rollback to cycle 5 is not data-restoring** → Because old data is intentionally discarded, rollback can restore the previous image/checkpoint but cannot recover the old schema contents unless external backups exist.

## Migration Plan

1. Update the Frontier Indexer module with an idempotent schema reset service ordered before the indexer container.
2. Configure Habiki for image `ghcr.io/ocky-public/frontier-indexer:v0.3.7`, `firstCheckpoint = "352596413"`, and reset generation `6`.
3. Validate Nix syntax/evaluation for Habiki.
4. Deploy with `./scripts/play.sh --limit habiki --tags frontier-indexer`.
5. Verify systemd units: TimescaleDB active, reset service completed, preflight succeeded, indexer active.
6. Verify logs do not contain database setup failures and metrics are scraped from the upgraded indexer.

Rollback:

- Revert the image/checkpoint/reset-generation changes and redeploy Habiki with the same targeted command.
- Do not decrement or remove the reset generation without considering whether it will trigger another reset; preserve marker semantics during rollback.
- Treat old cycle 5 indexed data as unrecoverable unless restored from backup.

## Open Questions

- Should `0.3.7` become the module default image or remain a Habiki-specific override until another host needs Frontier Indexer?
- Does the `0.3.7` container require explicit `PIPELINES` or `pipelines.toml` in practice, despite docs indicating unset `PIPELINES` runs all pipelines?
