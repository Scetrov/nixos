# Grafana Operations Portal

The Grafana operations portal is managed declaratively from source control.

## Source Of Truth

- Grafana datasources, authentication, and reverse proxy plumbing live in `src/roles/nixos/files/etc/nixos/modules/grafana.nix` and the related NixOS modules that expose Loki, Mimir, Tempo, Pyroscope, and Caddy routes.
- Grafana folders and dashboard resources live in `terraform/grafana.tf`.
- Dashboard JSON lives in `terraform/dashboards` and is the source of truth for the operations portal catalog.
- Service telemetry ownership stays with the service module plus `src/roles/nixos/files/etc/nixos/modules/alloy.nix` and `src/roles/nixos/files/etc/nixos/modules/prometheus.nix`.

## Folder Structure

- `Operations / Platform`: shared entrypoints and fleet-wide health dashboards.
- `Operations / Services`: per-service dashboards and deep links.

## Naming And UID Rules

- Platform dashboard UIDs use the `ops-` prefix.
- New service dashboard UIDs use the `svc-` prefix.
- Existing dashboard UIDs remain unchanged when they are already provisioned or referenced elsewhere.
- File names in `terraform/dashboards` should match the dashboard slug where practical.

## Minimum Observability Contract

- Metrics should expose a stable `service` label and preserve the existing `host` label when the runtime supports per-service scraping.
- Logs should expose stable `service` and `host` labels through Alloy relabeling.
- Traces should emit `service.name` and a host attribute such as `host.name` when the application can send OTLP spans.
- Profiles should use the same service identity as traces when profiling is added.

## Phase-One Signal Coverage

- `frontier-indexer`: metrics and logs available now; traces and profiles are not yet present.
- `dependency-track`: metrics and logs available after Prometheus scrape onboarding; traces and profiles are not yet present.
- `oncall`: logs available now; metrics exporter, traces, and profiles are not yet present.
- `hermes`: logs and external UI available now; metrics, traces, and profiles are not yet present.
- `home-assistant`: logs and external UI available now; metrics and traces remain follow-up work defined in the Home Assistant platform spec.
