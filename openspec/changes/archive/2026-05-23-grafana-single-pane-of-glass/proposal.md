## Why

The repository already centralizes observability traffic behind Grafana, Authentik, Caddy, Mimir, Loki, Tempo, and Pyroscope, but operators still rely on a small dashboard set and inconsistent per-service telemetry coverage. We need a clean end-state proposal that turns Grafana into the default operational entrypoint for the estate instead of a backend browser plus a few isolated dashboards.

## What Changes

- Add a Grafana operations landing experience with platform-wide overview dashboards and a service catalog dashboard.
- Define per-service dashboards and drilldown paths from summary views into metrics, logs, traces, profiles, incidents, and external service UIs where applicable.
- Establish a minimum observability contract for managed services so metrics, logs, and traces can be correlated by stable service and host identity.
- Expand telemetry onboarding for services that currently have partial or missing Grafana coverage.
- Standardize dashboard organization and declarative management so the single-pane experience remains reproducible from source control.

## Capabilities

### New Capabilities
- `grafana-operations-portal`: Makes Grafana the primary operator portal with platform overview, service catalog, per-service dashboards, and cross-signal drilldowns.

### Modified Capabilities
None.

## Impact

- Affects Grafana dashboard definitions and provisioning under the existing NixOS and OpenTofu workflows.
- Touches observability-related modules such as Grafana, Caddy, Alloy, Prometheus, and service modules that need telemetry onboarding.
- Adds new dashboard and folder structure conventions for platform-wide and service-specific views.
- Requires validation across the observability stack on `habiki`, including auth, routing, dashboard loading, and signal correlations.
