## 1. Declaration

- [x] 1.1 In `src/roles/nixos/files/device-configuration/habiki.nix`, change `scetrov.services.frontier-indexer.ingestConcurrencyMax` from `2` to `32`
- [x] 1.2 Confirm no other host or the reusable module default is modified (module default stays `null`)

## 2. Local validation

- [x] 2.1 Lint/evaluate the NixOS configuration for `habiki` (same gate the `nixos` play tag runs) to confirm the declaration is well-formed
- [x] 2.2 Verify the rendered `frontier-indexer` env script would emit `INGEST_CONCURRENCY_MAX=32` (eval the `indexerPrepareEnvScript` output or the equivalent nixos-rebuild dry-run)

## 3. Deployment

- [x] 3.1 Deploy to Habiki only: `./scripts/play.sh --limit habiki --tags frontier-indexer`
- [x] 3.2 On Habiki, confirm `/var/lib/frontier-indexer/indexer.env` contains `INGEST_CONCURRENCY_MAX=32`
- [x] 3.3 Confirm `podman-frontier-indexer` restarted cleanly and `frontier-indexer-db-preflight`/`schema-reset` did NOT run a reset (marker unchanged, still generation 7)

## 4. Verification (telemetry)

- [x] 4.1 Observe `cps=` in the `sequential_committer` watermark logs climbing from ~10–11 toward 30–60 (Grafana/Loki, ~15–30 min window)
- [x] 4.2 Confirm no `429` / transient-retry / `Checkpoint not found, retrying` bursts in Loki during the ramp
- [x] 4.3 Confirm `frontier_frontier_indexer_db_connections` stays under the pool cap and `db_connect_waited` stays low. Note: the `frontier-indexer-prepare-env` unit change propagates a stop/restart of `podman-frontier-timescaledb`, so `db_connections` will briefly zero during the deploy; start this observation window only after the DB is back up.
- [x] 4.4 Confirm the checkpoint backlog is shrinking using the `sequential_committer` watermark `cps=` in Loki plus a one-off live-head query to `https://graphql.testnet.sui.io/graphql` (the `frontier_indexer_chain_head_checkpoint` exporter is deferred/broken, so do not rely on it for this check)

## 5. Rollback readiness

- [x] 5.1 Document the rollback value path (lower to `16`, or `2`) and confirm no data/schema impact on rollback (verify reset marker still 7 and DB untouched)

## 6. Sign-off

- [x] 6.1 All changed files staged for commit (Staging Rule)
- [x] 6.2 No secrets/keys in changed files (Toxic Waste Rule)
- [x] 6.3 Commit with attribution (`Co-Authored-By: <active model>`, `Co-Authored-By: Pi Coding Agent`)
- [x] 6.4 Record deferred follow-ups (v0.4.1 image roll ~2026-10-22; chain-head exporter JSON-RPC→GraphQL fix) in a tracked place for later pickup
