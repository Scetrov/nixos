# System Resource Monitoring Specification

## ADDED Requirements

### Requirement: Declarative Grafana Dashboard Provisioning

The system SHALL declare the resource monitoring Grafana dashboard under the custom NixOS module configurations in `src/roles/nixos/files/etc/nixos/modules/grafana.nix` so it is provisioned automatically.

#### Scenario: Dashboard registered in Grafana config
- **WHEN** Grafana configuration is evaluated
- **THEN** the system registers the resource monitoring dashboard JSON definition under the declarative provisioning path

### Requirement: Dynamic Host Variable Dropdown

The dashboard SHALL include a template dropdown variable named `$host` that queries Prometheus/Mimir for all unique values of the `host` label to dynamically select machines (e.g., `fyne`, `habiki`, `bullit`).

#### Scenario: Host template variable populated
- **WHEN** the dashboard is loaded by an operator in the Grafana UI
- **THEN** the template variable dropdown named `host` executes a dynamic query for `host` label values against the default Prometheus/Mimir datasource with UID `"mimir"`

### Requirement: Isolate PromQL Host Telemetry

The dashboard SHALL filter all Prometheus metrics in the CPU, Memory, and Disk panels using `{host="$host"}` to correctly isolate telemetry emitted by the Alloy node-exporter configurations.

#### Scenario: Resource utilization query isolates host
- **WHEN** any resource panel (CPU, Memory, or Disk) is rendered on the dashboard
- **THEN** it executes a PromQL query that includes the `{host="$host"}` label matcher to target the active host selection
