## 1. Module Preparation

- [x] 1.1 Inspect `src/roles/nixos/files/etc/nixos/modules/frontier-indexer.nix` service ordering, env generation, and existing database preflight to identify the safest insertion point for schema reset.
- [x] 1.2 Add a Frontier Indexer module option for idempotent schema reset generation, using `null` as the default disabled state.
- [x] 1.3 Add a schema reset marker path under `/var/lib/frontier-indexer` so an already-applied generation is not repeated on restart or rebuild.

## 2. Schema Reset Implementation

- [x] 2.1 Implement a non-secret schema reset script that reads the generated runtime env, validates `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, and `DB_SCHEMA`, and refuses to operate on an empty schema name.
- [x] 2.2 Make the reset script drop and recreate only the configured `indexer` schema, then write the applied reset generation marker after successful SQL execution.
- [x] 2.3 Add a `frontier-indexer-schema-reset.service` oneshot unit ordered after TimescaleDB readiness and before `podman-frontier-indexer.service`.
- [x] 2.4 Update `podman-frontier-indexer.service` dependencies so the indexer cannot start until the reset service and database preflight have completed successfully.

## 3. Habiki Cycle 6 Configuration

- [x] 3.1 Configure Habiki's Frontier Indexer image as `ghcr.io/ocky-public/frontier-indexer:v0.3.7` using the module option or updated module default.
- [x] 3.2 Change Habiki's Frontier Indexer `firstCheckpoint` to `"352596413"`.
- [x] 3.3 Set Habiki's schema reset generation to `6` so cycle 5 data is discarded once for the cycle 6 upgrade.
- [x] 3.4 Confirm the deployment does not need `pipelines.toml` or explicit `PIPELINES`; if implementation discovers it is required, add declarative pipeline configuration before deployment.

## 4. Validation

- [x] 4.1 Run repository formatting or syntax checks relevant to the modified Nix files.
- [x] 4.2 Evaluate or build the Habiki NixOS configuration far enough to catch module option, systemd dependency, and script interpolation errors.
- [x] 4.3 Review generated scripts or evaluated unit fragments for accidental logging or embedding of database secrets.

## 5. Deployment and Verification

- [x] 5.1 Deploy the change with `./scripts/play.sh --limit habiki --tags frontier-indexer`.
- [x] 5.2 Verify `frontier-indexer-schema-reset.service` completed and recorded reset generation `6` without exposing credentials.
- [x] 5.3 Verify `frontier-indexer-db-preflight.service`, `podman-frontier-timescaledb.service`, and `podman-frontier-indexer.service` are healthy on Habiki.
- [x] 5.4 Verify the generated indexer environment contains `FIRST_CHECKPOINT=352596413` and the running container uses `ghcr.io/ocky-public/frontier-indexer:v0.3.7` without printing secrets.
- [x] 5.5 Verify recent Frontier Indexer logs contain no `Failed to get connection for database setup` failures and metrics are available through the managed Prometheus/Grafana path.

## 6. Sign-off

- [x] 6.1 Check `git diff` for unintended changes and secret material.
- [x] 6.2 Stage all required files for commit according to the repository staging rule.
- [x] 6.3 Record any rollback notes or operational caveats discovered during deployment verification.

## Operational Notes

- Deployment verification confirmed `frontier-indexer-schema-reset.service` is a successful oneshot and therefore reports `ActiveState=inactive`, `Result=success`, `ExecMainStatus=0` after completion.
- Reset generation marker is `/var/lib/frontier-indexer/schema-reset-generation` and contained `6`; repeated starts skipped the reset as intended.
- Rollback can revert image/checkpoint/reset generation declaratively, but discarded cycle 5 schema contents are not recoverable without backup.
