# Fix Frontier Indexer ingest concurrency cap

## Why

Habiki's Frontier Indexer is permanently behind the Sui testnet chain head. Live telemetry shows steady ingestion of ~10–11 checkpoints/second against a public checkpoint store that serves ~10 KB files in <0.1 s with no observed 429s, while TimescaleDB's connection pool sits ~97% idle. The cap is our own deployment declaration, `INGEST_CONCURRENCY_MAX=2` (introduced 2026-05-30 in `6438a90` and carried through the E6C7 cutover), against an upstream default of 500. The resulting backlog (~2M checkpoints) is shrinking at only ~5–7 cps net and would otherwise take weeks to clear.

## What Changes

- Raise `scetrov.services.frontier-indexer.ingestConcurrencyMax` on Habiki from `2` to `32` in `src/roles/nixos/files/device-configuration/habiki.nix`.
- Deploy through the existing automation (`./scripts/play.sh --limit habiki --tags frontier-indexer`) and verify the catch-up rate in Loki/Prometheus.
- Record two explicitly **deferred** follow-ups (out of scope here):
  - Roll the image from `v0.4.0` to `v0.4.1` after its seven-day release-age window (~2026-10-22); `v0.4.1` is a same-cycle additive change (protocol 139, new `address_aliases` migration) requiring no schema reset.
  - Repoint the chain-head exporter probe from the deprecated public JSON-RPC endpoint to the public GraphQL endpoint (`https://graphql.<network>.sui.io/graphql`); `frontier_indexer_chain_head_scrape_success` has been `0` since Sui deprecated JSON-RPC on public fullnodes.

## Capabilities

### New Capabilities
- `frontier-indexer-ingestion`: Steady-state checkpoint ingestion configuration on Habiki — ingestion source, concurrency declaration, and a throughput floor sufficient to keep the indexed chain head from drifting from live testnet.

### Modified Capabilities
<!-- No existing capability's requirements change; frontier-indexer-cycle-management (image pin, reset safety) is untouched. -->

## Impact

- `src/roles/nixos/files/device-configuration/habiki.nix` — one declaration change.
- Regenerated runtime env file on Habiki (`/var/lib/frontier-indexer/indexer.env`) picks up `INGEST_CONCURRENCY_MAX=32`; the existing `frontier-indexer-prepare-env.service` ordering applies it and `podman-frontier-indexer` restarts. No database or schema impact (reset generation marker unchanged).
- Upstream load: up to 32 parallel checkpoint-file GETs against `checkpoints.testnet.sui.io`; S3-backed and comfortably within per-client limits. Failure mode if throttled: 429 backoff in logs — observable and reversible by lowering the value to 16.
- No changes to the reusable module defaults (`ingestConcurrencyMax` stays `null` there), no API, dependency, or image changes.
