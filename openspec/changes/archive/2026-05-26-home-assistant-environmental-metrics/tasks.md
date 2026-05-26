# Home Assistant Environmental Metrics Tasks

## 1. Export And Secret Wiring

- [x] 1.1 Add an age-backed Home Assistant metrics token secret using the repository's existing `/root/secrets/*.age` pattern and document how the token is created for local Prometheus scraping
- [x] 1.2 Extend `src/roles/nixos/files/etc/nixos/modules/home-assistant.nix` so the generated `configuration.yaml` enables Home Assistant's internal Prometheus integration declaratively
- [x] 1.3 Configure the Home Assistant Prometheus integration with an explicit include list for the approved temperature, humidity, CO2, PM2.5, PM10, and air-quality entities discovered on `habiki`

## 2. Local Scrape Path

- [x] 2.1 Add a Home Assistant scrape job through the Home Assistant module using the existing `services.prometheus.scrapeConfigs = lib.mkAfter [ ... ]` pattern
- [x] 2.2 Configure the scrape job to use the local Home Assistant listener, the correct metrics path, token-backed authorization, and stable `service=home-assistant` labeling
- [x] 2.3 Validate locally that the Home Assistant metrics endpoint responds correctly and that Prometheus reports the Home Assistant target as healthy after deployment

## 3. Dashboard Buildout

- [x] 3.1 Replace the metrics placeholder content in `terraform/dashboards/home-assistant-service.json` with real operational panels for scrape health and related Home Assistant service signals
- [x] 3.2 Add a new declarative Grafana dashboard JSON file for Home Assistant environmental telemetry covering temperature, humidity, CO2, PM2.5, and PM10 history
- [x] 3.3 Register the new Home Assistant environmental dashboard in `terraform/grafana.tf` and keep it grouped under the existing Operations / Services folder structure

## 4. End-To-End Verification

- [x] 4.1 Deploy the NixOS changes narrowly to `habiki` using the existing targeted workflow and confirm Home Assistant and Prometheus are both healthy afterward
- [x] 4.2 Verify that the new Home Assistant environmental metrics are queryable from both the local Prometheus datasource and the retained Mimir datasource in Grafana
- [x] 4.3 Apply the Grafana dashboard changes through `./scripts/tofu.sh` and verify both the Home Assistant service dashboard and the environmental dashboard render live telemetry without empty placeholder panels
