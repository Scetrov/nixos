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

## Release follow-up superseded

The old v0.4.1 cooldown reminder is superseded: Habiki now declares digest-pinned
v0.5.0. Do not deploy the historical v0.4.1 target from this note. Continue to
review release compatibility and preserve generation `7` for non-reset changes;
configuration inspection alone is not a live rollout check.

## Fix the chain-head exporter probe

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
