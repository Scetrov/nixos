# Home Assistant Environmental Metrics Proposal

## Why

Home Assistant on habiki already has live temperature, humidity, CO2, PM2.5, PM10, and air-quality entities, but those signals are not yet exported into the existing Prometheus and Mimir path or surfaced in Grafana. Closing that gap now gives the environment a declarative, end-to-end telemetry path for indoor climate and air-quality monitoring using the same observability stack and dashboard workflows already used elsewhere in the repo.

## What Changes

- Extend the managed Home Assistant runtime configuration to enable the internal Prometheus exporter for a curated set of environmental entities.
- Add a local Prometheus scrape job for Home Assistant on habiki using an age-backed long-lived access token and stable service labels aligned with the existing observability contract.
- Add verification steps that prove the Home Assistant metrics endpoint is reachable locally, Prometheus scrapes it successfully, and the resulting metrics are queryable through Mimir and Prometheus.
- Replace the placeholder Home Assistant service dashboard content with operational scrape-health coverage and add dashboard panels for environmental telemetry such as temperature, humidity, CO2, PM2.5, and PM10.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `home-assistant-platform`: expand the platform requirements to cover managed Prometheus export configuration, secure local scraping, and environmental telemetry validation for Home Assistant.
- `grafana-operations-portal`: expand the portal requirements so the Home Assistant service dashboard includes real metrics-backed operational and environmental views instead of a metrics placeholder.

## Impact

- Affected NixOS modules: `src/roles/nixos/files/etc/nixos/modules/home-assistant.nix` and `src/roles/nixos/files/etc/nixos/modules/prometheus.nix`.
- Affected secrets flow: a new age-backed Home Assistant metrics token will need to be provisioned for local Prometheus scraping.
- Affected Grafana assets: `terraform/dashboards/home-assistant-service.json` and at least one additional Home Assistant environmental dashboard managed through `terraform/grafana.tf`.
- Affected runtime systems: Home Assistant, Prometheus, Mimir, and Grafana on `habiki`.
