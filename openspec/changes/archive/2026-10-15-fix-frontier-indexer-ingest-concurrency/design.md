## Context

Habiki runs the Frontier Indexer (`ghcr.io/algo-net/frontier-indexer:v0.4.0`) ingesting Sui **testnet** checkpoints into a dedicated TimescaleDB. Ingestion uses the `store` source — each checkpoint is a ~10 KB `.binpb.zst` object fetched over HTTPS from the public S3-backed `checkpoints.testnet.sui.io` — governed by `INGEST_CONCURRENCY_MAX`, which caps how many checkpoint objects the indexer fetches in flight.

Current state (observed 2026-10-15):

- `INGEST_CONCURRENCY_MAX=2` (our declaration; upstream default `500`).
- Steady ingest ~10–11 cps; TimescaleDB pool ~35/36 idle; `db_connect_waited` barely moving.
- No 429 / backoff / `Checkpoint not found` storms in 24 h of Loki logs.
- Chain head ahead by ~2M checkpoints; net gap shrink ~5–7 cps.

The DB write side is clearly not the ceiling (idle pool, low connection wait). The ceiling sits at the fetch step, and it is set by our own concurrency declaration, not by the upstream store.

## Goals / Non-Goals

**Goals:**
- Raise the effective ingest throughput so the backlog (~2M checkpoints) clears in ~12–24 h rather than weeks.
- Keep the running indexer healthy (DB pool, CPU, upstream load) and the change fully reversible.
- Do it without touching the image pin, the database, or the schema-reset marker.

**Non-Goals:**
- Rolling to `v0.4.1` (deferred to its ~2026-10-22 seven-day window; additive, no reset).
- Fixing the broken chain-head exporter probe (deferred; separate concern).
- Switching the ingestion `source` from `store` to `fullnode`/gRPC.
- Changing the reusable module default (`ingestConcurrencyMax` stays `null` so other hosts are unaffected).
- Provisioning our own Sui full node or a dedicated RPC provider.

## Decisions

### Raise `ingestConcurrencyMax` to 32 on Habiki only

Set `scetrov.services.frontier-indexer.ingestConcurrencyMax = 32` in `habiki.nix`, leaving the module default `null`. This is the single knob that maps to the fetch-step ceiling.

- **Why 32, not the upstream default 500:** 32 already gives ~16× the current fetch parallelism (≈30–60 cps headroom vs ~4 cps chain production), is conservative on upstream CDN load, and keeps a large safety margin if the store or our DB shows stress. 500 is unbounded headroom we do not need to keep-up-time and would be a large unobserved jump. 16 was the fallback considered; 32 gives faster catch-up while still conservative.
- **Why Habiki-only:** the module default change would affect any future host. This is a machine-tuning decision, not a contract change.

**Alternatives considered:**
- *Switch `ingestionSource` to `fullnode` (gRPC streaming):* rejected — the public gRPC/JSON-RPC endpoints are explicitly rate-limited "development / public-good" endpoints and JSON-RPC is now deprecated on public fullnodes; we would need a dedicated full node or provider, which is disproportionate for a catch-up.
- *Leave at 2 and wait:* rejected — ~weeks to clear, and the gap would keep drifting.

### Deploy via existing targeted automation, verify against live telemetry

Use `./scripts/play.sh --limit habiki --tags frontier-indexer`. The `frontier-indexer-prepare-env` oneshot regenerates `/var/lib/frontier-indexer/indexer.env` with the new value; because that oneshot's unit changes, NixOS restarts it, and its `Requires=` dependency propagates a stop/restart of both `podman-frontier-indexer` and `podman-frontier-timescaledb` (a brief DB blip — no data or schema impact). No schema reset because the reset generation marker is unchanged.

Verification is against **observed** signals, not just exit status:
- `cps=` in the `sequential_committer` watermark log lines climbs from ~10–11 toward 30–60.
- No `429` / `retry_on_transient` / `Checkpoint not found, retrying` bursts in Loki.
- `frontier_frontier_indexer_db_connections` stays well under pool cap; `db_connect_waited` stays low.
- Backlog gap drops by ~`concurrency - chain_rate` × seconds.

## Risks / Trade-offs

- [CDN throttling at 32× load] → Observed via 429/backoff log lines and a flatlined `cps`. Mitigation: lower `ingestConcurrencyMax` to 16 and redeploy; purely declarative, no data impact.
- [DB write pressure as ingest rate rises] → TimescaleDB shows ~97% idle pool now; monitor `db_connections`/`db_connect_waited`/latency during the first catch-up hour. Mitigation: same rollback path (drop concurrency).
- [Higher sustained egress/bandwidth on Habiki] → Negligible: ~30 cps × 10 KB ≈ 300 KB/s peak during catch-up, tapers to ~4 cps once caught up.
- [Transient deploy disruption while the indexer restarts] → Standard, brief; ingestion resumes from its persisted watermark, no data loss.

## Migration Plan

1. Update `habiki.nix` (`ingestConcurrencyMax = 32`).
2. Run targeted deployment: `./scripts/play.sh --limit habiki --tags frontier-indexer`.
3. Confirm the regenerated `indexer.env` on Habiki contains `INGEST_CONCURRENCY_MAX=32` and the indexer container restarted cleanly.
4. Watch telemetry for ~15–30 min: `cps` climb, no 429 bursts, DB pool healthy.
5. Let it run; track the backlog clearing toward the live chain head.

**Rollback:** set `ingestConcurrencyMax = 16` (or back to `2`) and re-run the same targeted deployment. No data or schema changes are made, so rollback is clean and safe at any point.

## Open Questions

- None blocking. The only follow-up decision is whether, after catch-up, to tune `ingestConcurrencyMax` down toward a steady-state value (e.g. 8–16) to minimize upstream load — revisit once the backlog is cleared.
