# Frontier Indexer — Deferred Follow-ups

Tracked here for later pickup. Originated by the
`fix-frontier-indexer-ingest-concurrency` change (ingest concurrency raised
from 2 to 32 on Habiki).

## Rollback path (if ingest shows stress)

The change is a single declarative knob with no data or schema impact. To roll back:

1. Lower `scetrov.services.frontier-indexer.ingestConcurrencyMax` in
   `src/roles/nixos/files/device-configuration/habiki.nix` to `16` (or back to `2`).
2. Re-run the same targeted deployment:
   `./scripts/play.sh --limit habiki --tags frontier-indexer`.
3. The indexer resumes from its persisted watermark at the lower concurrency.

**No database or schema reset is triggered** by changing this value — the
`resetSchemaGeneration` marker stays `7` and the DB is untouched. (Verified post-
deploy: marker `7` unchanged, `frontier-indexer-schema-reset` logged
"skipped: no new generation".)

## 1. Roll `frontier-indexer` image to v0.4.1

- **When:** ~2026-10-22, after the seven-day release-age window for v0.4.1 has
  elapsed.
- **What:** Bump the pinned image in
  `src/roles/nixos/files/device-configuration/habiki.nix`
  (`scetrov.services.frontier-indexer.indexerImage`) from `v0.4.0` to `v0.4.1`,
  updating the `sha256:` digest to the new image digest.
- **Impact:** v0.4.1 is a same-cycle additive change (protocol 139, new
  `address_aliases` migration) and requires **no schema reset**. The reset
  generation marker must stay unchanged (currently `7`).
- **Deploy:** `./scripts/play.sh --limit habiki --tags frontier-indexer`.

## 2. Fix the chain-head exporter probe

- **What:** Repoint the `frontier_indexer_chain_head_checkpoint` exporter probe
  from the deprecated public JSON-RPC endpoint to the public GraphQL endpoint
  (`https://graphql.<network>.sui.io/graphql`).
- **Why:** `frontier_indexer_chain_head_scrape_success` has been `0` since Sui
  deprecated JSON-RPC on public fullnodes, so the exporter cannot report the
  live chain head. Until fixed, backlog/gap checks must use the
  `sequential_committer` watermark `cps=` in Loki plus a one-off live-head
  query to `https://graphql.testnet.sui.io/graphql`.
- **Deploy:** update the exporter/Alloy probe config, then a targeted deploy to
  Habiki.
