# System Resource Monitoring Dashboard Proposal

## Why

We currently lack a centralized, declarative dashboard in Grafana to monitor system resource consumption (CPU, Memory, and Disk utilization) dynamically across our NixOS cluster machines (`fyne`, `habiki`, and `bullit`). Adding a declarative dashboard dynamically filtered by host will automate cluster health visibility and avoid manual dashboard configuration overhead.

## What Changes

- Update `src/roles/nixos/files/etc/nixos/modules/grafana.nix` to declaratively provision a new Grafana dashboard for system resource monitoring.
- Implement a dynamic `$host` template variable dropdown in the dashboard that queries unique `host` label values from the Prometheus/Mimir datasource (UID `"mimir"`).
- Configure resource visualization panels (CPU, Memory, and Disk) to filter metrics using `{host="$host"}` to isolate telemetry emitted by the Alloy node-exporter configurations.

## Capabilities

### New Capabilities

- `grafana-resource-monitoring`: Declarative Grafana dashboard for dynamic system resource (CPU, Memory, Disk) monitoring across cluster nodes utilizing Mimir/Prometheus datasource label queries.

### Modified Capabilities

None.

## Impact

- **Affected Code:** Modifies `src/roles/nixos/files/etc/nixos/modules/grafana.nix` to register the new dashboard JSON structure.
- **Affected Services:** Rebuilds Grafana on the `habiki` node to load the newly provisioned dashboard.
- **No breaking changes or external API updates.**
