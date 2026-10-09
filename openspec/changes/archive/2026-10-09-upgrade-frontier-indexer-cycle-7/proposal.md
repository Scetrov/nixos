## Why

Habiki is still configured for Frontier Indexer Cycle 6, while upstream v0.4.0 provides the Cycle 7 contracts and checkpoint under the Algo-Net image namespace. Cycle 6 indexed data and runtime artifacts are disposable, so the transition should start cleanly without retaining obsolete state or risking repeated resets.

## What Changes

- Deploy `ghcr.io/algo-net/frontier-indexer:v0.4.0` pinned by SHA256 digest, with `FIRST_CHECKPOINT=387251154` on Sui testnet.
- Verify the release indexes the supplied Cycle 7 asset and world contracts using its compiled package configuration.
- **BREAKING**: Discard Cycle 6 indexed data through reset generation `7`; remove any confirmed cycle-specific runtime artifacts through bounded automation without creating a Cycle 6 archive.
- Authenticate to TimescaleDB before reset, stop the old indexer writer before destructive operations, and refuse stale reset generations.
- Preserve the managed database cluster, credentials, network, endpoints, logging and metrics integrations.
- Align the reusable module image default with the selected release so it no longer points at the old namespace.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `frontier-indexer-cycle-management`: Require Cycle 7 image/checkpoint/contracts, digest pinning, safe once-per-generation reset and bounded old-cycle cleanup, with deployment verification.

## Impact

- `src/roles/nixos/files/device-configuration/habiki.nix`: image, checkpoint and reset generation.
- `src/roles/nixos/files/etc/nixos/modules/frontier-indexer.nix`: image default, authenticated startup ordering and reset safety.
- Ansible orchestration if required to stop the old writer and remove inventoried Cycle 6 artifacts safely during targeted deployment.
- Habiki's `indexer` PostgreSQL schema is destroyed and recreated; old indexed data is not recoverable through configuration rollback.
- Existing Grafana dashboards, Prometheus scrapes and Alloy log integration require compatibility verification, not a redesign.
- No new credentials, ports, identity integrations or service routes are introduced.
