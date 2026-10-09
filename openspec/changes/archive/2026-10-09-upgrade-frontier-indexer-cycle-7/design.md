## Context

Habiki enables Frontier Indexer through `src/roles/nixos/files/device-configuration/habiki.nix`, currently with v0.3.7 in the Ocky-Public namespace, checkpoint `352596413`, ingestion concurrency `2`, and reset generation `6`. The reusable module default is older still (v0.3.5). The module maintains a dedicated Podman network, TimescaleDB cluster, runtime secrets/environment, schema reset marker, readiness and authentication checks, metrics and chain-head exporter.

Upstream v0.4.0 is the Cycle 7 release. Its `src/lib.rs` contains precisely these testnet world-package addresses:

- Asset: `0xc663658ff707985246bc7b5c605a458ec2caea28bfc35c253eb526dcf961643e`
- World: `0x7be18d6294e533bedd9a5d70a96ce8d9d4b87a7c74188ba65d3fe966bbed9d92`

Its `.env.sample` starts at `387251154`. Registry inspection during exploration resolved `ghcr.io/algo-net/frontier-indexer:v0.4.0` to manifest digest `sha256:20c64a1c96fa96c29569fa8343398566d22cb17fb62b1dd8ee6a0d21d7af5fc9` with a Linux amd64 image. Revalidate these facts at implementation time, including repository release-age policy.

The user explicitly permits discarding all previous-cycle data and artifacts. No additional cycle-specific runtime mounts appear in the current module, but live state has not been inventoried. The present startup ordering resets before authenticated preflight, and the reset marker treats any unequal generation as permission to erase data.

## Goals / Non-Goals

**Goals:**

- Start clean Cycle 7 indexing from the supplied checkpoint with a digest-pinned compatible image.
- Discard Cycle 6 indexed state and confirmed cycle-specific runtime artifacts without preserving a Cycle 6 archive.
- Make reset idempotent, authenticated, writer-safe and resistant to stale-generation rollback.
- Keep the stable schema name, secret source and existing observability integrations.
- Make the transition reproducible through targeted NixOS/Ansible automation.

**Non-Goals:**

- Preserve or restore Cycle 6 indexed data.
- Delete the entire PostgreSQL cluster, unrelated schemas, shared container storage or monitoring history.
- Delete archived OpenSpec documents or Git history; these are project records, not indexed runtime artifacts.
- Upgrade TimescaleDB, redesign dashboards, add transports or alter external access.

## Decisions

### Pin the Cycle 7 release and use compiled package configuration

Declare `ghcr.io/algo-net/frontier-indexer:v0.4.0@sha256:20c64a1c96fa96c29569fa8343398566d22cb17fb62b1dd8ee6a0d21d7af5fc9` in Habiki and align the module default. Retain testnet, `PACKAGES=app,world`, all-pipeline behavior and concurrency `2` unless compatibility testing demonstrates a specific required change. Set the checkpoint to `387251154` and reset generation to `7`.

The supplied addresses are compiled into this release, not passed through invented environment variables. Verify the pinned image corresponds to the release source and package configuration before deployment. Reject mutable `latest` and tag-only references because they do not provide content integrity.

### Reuse a bounded schema reset rather than wipe the cluster

Retain `DB_SCHEMA=indexer` and drop/recreate that schema once for generation `7`. Forward the SQL heredoc using `podman run -i`; isolated implementation testing showed that the inherited invocation without stdin forwarding could publish a marker without executing SQL. Verify actual schema removal, not just the process exit status or marker. Inspect actual schema placement, including migration and watermark bookkeeping, to confirm no previous-cycle application state survives outside it. Any required additional cleanup must be explicitly identified and automated before proceeding; never broaden deletion to the entire state directory speculatively.

Inventory caches, dumps or exports associated with this deployment. Remove only confirmed obsolete artifacts from an explicit allowlist with validated paths and appropriate service shutdown. Do not use global Podman pruning. An empty inventory is a valid outcome and needs no new cleanup mechanism.

The cluster, database credentials, runtime environment and reset marker remain managed infrastructure. Schema reuse avoids changing consumers; full cluster deletion risks unrelated state and is unnecessary without evidence.

### Authenticate before reset and exclude the old writer

Arrange startup as readiness → authenticated preflight → schema reset → indexer. Remove the current preflight dependency on reset to avoid a systemd dependency cycle. The existing secret synchronization remains available before destructive SQL.

During the generation transition, ensure the existing indexer process has stopped before reset starts, using declarative systemd coordination or narrowly targeted Ansible orchestration as established by evaluation and transition testing. Merely declaring reset `before` the new indexer is insufficient evidence that an already-running old writer is stopped.

Reset failure must prevent the indexer from starting. Preserve journal collection for any renamed or added units.

### Use monotonic, fail-closed generation handling

A missing marker permits the first configured reset. An equal marker skips reset. A valid lower marker permits advancement. A higher marker rejects a stale request without dropping data or starting the stale indexer. Invalid marker contents fail closed. A null generation disables reset but must not be used to bypass a stale-generation guard during rollback.

Keep the marker outside the reset schema and publish it atomically only after successful reset. If reset succeeds but marker publication fails, fail startup; retry may repeat the reset while no indexer has started, but must never claim success without a durable marker. Serialize reset execution so concurrent starts cannot race.

A filesystem marker is not transactional with PostgreSQL. Coordinated database/marker backup and recovery remain necessary; do not describe the marker as a complete disaster-recovery guarantee.

## Risks / Trade-offs

- [Irreversible old-cycle loss] → Explicitly authorized; do not promise rollback restores deleted data.
- [Old writer remains active during reset] → Test transition from a running old configuration, not only cold boot ordering.
- [Marker downgrade causes another reset] → Reject stale generations and verify the schema remains intact.
- [Password mismatch blocks reset] → Authenticate and synchronize credentials before resetting; keep secrets out of logs.
- [Cleanup removes unrelated state] → Inventory first; validate explicit paths and avoid cluster/global deletion.
- [Release changes pipelines or metrics] → Test the actual pinned image against disposable TimescaleDB and verify dashboard query compatibility.
- [External clients have open schema connections] → Identify active consumers before cutover; coordinate downtime where necessary.
- [Old NixOS generation contains unsafe reset code] → Do not activate the old generation after cutover; roll forward using current safety logic and Cycle 7 configuration.

## Migration Plan

1. Revalidate upstream release, digest, architecture, contracts and release eligibility. Inventory Habiki state and active consumers read-only.
2. Implement declarations, ordering, generation safeguards and any justified bounded cleanup through repository automation.
3. Exercise startup, a running-writer cycle transition, authentication repair, reset failures, retry, equal generation and stale/invalid markers using isolated disposable containers. Validate NixOS evaluation and generated systemd dependencies.
4. Deploy only with `./scripts/play.sh --limit habiki --tags frontier-indexer`; ensure the old writer is stopped before reset or cleanup.
5. Confirm generation `7`, clean application state, successful migrations and checkpoint progress from `387251154`. Verify service health, contract configuration, logs and Prometheus/Grafana signals.
6. Run configured pre-commit checks, archive this OpenSpec change before the final signed conventional commit/PR, and stage only reviewed files free of secrets. Ask the user to install the pre-commit hook if configured but absent.

Rollback is operational recovery, not recovery of Cycle 6 data: stop the indexer, retain generation `7` and current reset safeguards, and repair or deploy a tested Cycle 7-compatible image. Do not blindly activate a pre-transition NixOS generation or decrement the generation. Any future destructive reindex must use a separately declared higher generation.

## Open Questions

- Does the live deployment contain previous-cycle caches, dumps, exports or application bookkeeping outside `indexer`? Resolve through inventory before cleanup.
- Are external consumers active during the reset? Establish the downtime boundary before deployment.
- Which systemd/Ansible coordination best guarantees writer exclusion during a NixOS switch? Resolve with evaluation and a running-service transition test, preserving the requirements above.
