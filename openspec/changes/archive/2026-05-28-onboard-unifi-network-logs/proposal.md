## Why

UniFi UCG Ultra firewall, threat/IDS, and warning-level network logs are currently not retained or visible in the central observability stack, making network investigations depend on noisy manual UniFi log inspection. Shipping structured UniFi syslog into Loki and Grafana will provide fast, declarative dashboarding for recent network security and traffic events using the existing 7-day logging platform.

## What Changes

- Add a managed UniFi network log ingestion path from the UCG Ultra at `10.229.0.1` to `habiki` over a custom UDP syslog port.
- Restrict the receiver so only the UCG Ultra can send UniFi syslog traffic to `habiki` on the selected port.
- Introduce Vector as the UniFi-specific syslog receiver and parser, keeping the existing Alloy host/service telemetry path unchanged.
- Filter retained UniFi logs to firewall events, threat/IDS events, and warning-or-higher non-firewall events.
- Parse retained UniFi messages into structured Loki JSON fields for dashboard queries such as allow/block counts, top source/destination IPs, ports, protocols, threat events, and recent warning/error events.
- Add a declaratively managed Grafana dashboard for UniFi network log visibility.
- Document the required UniFi Network Application remote logging configuration for the UCG Ultra.
- Exclude GeoIP/country-map enrichment from this change to avoid paid/licensed database requirements.

## Capabilities

### New Capabilities
- `unifi-network-log-observability`: Covers UniFi UCG Ultra syslog ingestion, filtering, parsing, Loki labeling, dashboard visibility, and operator setup documentation.

### Modified Capabilities
- `grafana-operations-portal`: Adds UniFi network log visibility to the declaratively managed Grafana operations portal catalog.

## Impact

- NixOS modules under `src/roles/nixos/files/etc/nixos/modules/` for Vector-based UniFi syslog ingestion and firewall exposure on `habiki`.
- `src/roles/nixos/files/device-configuration/habiki.nix` to enable the UniFi log receiver if implemented as a host-scoped module.
- Existing Loki service on `habiki` as the local log destination; current 7-day retention remains unchanged.
- Grafana dashboard source under `terraform/dashboards/` and dashboard registration in `terraform/grafana.tf`.
- Operator documentation for UniFi Network Application remote logging setup.
- Deployment uses existing targeted workflows such as `./scripts/play.sh --limit habiki --tags nixos` and `scripts/tofu.sh` for Grafana resources.
