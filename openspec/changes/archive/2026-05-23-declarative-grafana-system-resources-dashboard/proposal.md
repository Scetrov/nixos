# Declarative Grafana System Resources Dashboard

## Why

The repository already provisions Grafana and Mimir declaratively, but system resource monitoring needs a formal contract to ensure the dashboard remains reproducible and correctly scoped by host. This change hardens the existing system resources dashboard so operators can select `fyne`, `habiki`, or `bullit` from a dynamic `$host` dropdown and inspect CPU, memory, and disk telemetry from the default Mimir datasource.

## What Changes

- Update `src/roles/nixos/files/etc/nixos/modules/grafana.nix` to provision a Grafana dashboard JSON definition through the existing NixOS and Ansible workflow.
- Ensure the dashboard provider writes `system-resources.json` under `/etc/grafana/dashboards`.
- Ensure the dashboard contains a template variable named `host` using datasource UID `mimir` and querying unique `host` label values.
- Ensure CPU, memory, and disk panels use PromQL expressions filtered with `{host="$host"}` so Alloy node-exporter telemetry is isolated to the selected machine.
- Keep the dashboard declarative, non-editable at the provisioning layer, and reproducible from source control.

## Capabilities

### New Capabilities

### Modified Capabilities

- `grafana-resource-monitoring`: Strengthen the resource monitoring dashboard requirements around dynamic host selection, Mimir datasource usage, and host-scoped CPU, memory, and disk panels.

## Impact

- Affects `src/roles/nixos/files/etc/nixos/modules/grafana.nix`.
- Uses existing Grafana provisioning and tmpfiles patterns.
- Uses the existing default Prometheus/Mimir datasource with UID `mimir`.
- Requires no new secrets, ports, Authentik resources, or external dependencies.
