## Why

The Operations Platform Overview dashboard is intended to be the fleet-level cockpit, but it currently gives an incomplete and partially incorrect view of fleet health. `Hosts Reporting` shows no data because it queries the stale `job="node"` target instead of the active fleet telemetry, and the dashboard only exposes CPU and memory while omitting storage, disk queue, and network pressure signals that are essential for operating the fleet.

## What Changes

- Fix the `Hosts Reporting` stat to use active fleet host telemetry from Mimir.
- Fill the unused top-row dashboard space with an additional observability stack health stat, such as Prometheus scrape health.
- Expand the Fleet Health section with fleet-level host panels for root disk usage, disk throughput, disk I/O operations, disk busy/queue pressure, and network error/drop signals.
- Keep the dashboard focused on fleet-wide host operations rather than per-service troubleshooting.
- Reuse proven node-exporter/Alloy metrics already present in the System Resources dashboard where possible.
- Validate dashboard PromQL against the live Mimir datasource before sign-off.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `grafana-operations-portal`: Strengthen the platform overview requirements so it functions as a fleet-level operations dashboard with accurate host reporting and storage/network pressure visibility.

## Impact

- Affected dashboard: `terraform/dashboards/platform-overview.json`
- Affected specification: `openspec/specs/grafana-operations-portal/spec.md`
- Data sources: Grafana Mimir datasource UID `mimir`; existing Alloy/node-exporter host metrics.
- Deployment path: existing OpenTofu/Grafana dashboard provisioning through `scripts/tofu.sh` and targeted playbook runs where applicable.
