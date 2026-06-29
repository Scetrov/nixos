## Why

Frontier Indexer has released `0.3.7` for EVE Frontier cycle 6, adding Inventory v2 events, rift data/events, updated cycle 6 indexed packages, and a table race-condition fix. Habiki currently runs the older cycle 5-era deployment, so it needs a controlled upgrade that starts from the cycle 6 checkpoint and safely discards the old indexed data.

## What Changes

- Upgrade the Habiki Frontier Indexer container image to `ghcr.io/ocky-public/frontier-indexer:v0.3.7`.
- Change Habiki's Frontier Indexer `FIRST_CHECKPOINT` value to `352596413` so indexing begins just before cycle 6 deployment.
- Add an automated, non-secret data reset path for the existing `indexer` schema so old cycle 5 data can be thrown away before the upgraded indexer starts.
- Preserve the existing TimescaleDB, Podman network, database preflight, metrics scraping, and Grafana observability integration.
- Verify the deployment through a targeted Habiki run using the existing `frontier-indexer` tag.

## Capabilities

### New Capabilities
- `frontier-indexer-cycle-management`: Declarative lifecycle management for Frontier Indexer cycle upgrades, including image/checkpoint selection and safe reset of disposable indexed data.

### Modified Capabilities
- `grafana-error-remediation`: Frontier Indexer database startup validation must continue to protect the upgraded cycle 6 deployment and avoid reintroducing database setup failures.

## Impact

- `src/roles/nixos/files/etc/nixos/modules/frontier-indexer.nix`: image default or option usage, environment generation, and reset/preflight orchestration.
- `src/roles/nixos/files/device-configuration/habiki.nix`: Habiki-specific cycle 6 checkpoint and any image/reset option values.
- Habiki runtime state under `/var/lib/frontier-indexer`, specifically the PostgreSQL `indexer` schema contents.
- `podman-frontier-indexer.service`, `podman-frontier-timescaledb.service`, and Frontier Indexer preflight/wait services.
- Prometheus/Grafana Frontier Indexer dashboards and Loki logs used for post-upgrade verification.
