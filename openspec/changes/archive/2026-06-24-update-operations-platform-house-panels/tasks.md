## 1. Discovery

- [x] 1.1 Inspect `terraform/dashboards/platform-overview.json` layout and choose a compact location for a House Environment section without disrupting existing platform/fleet panels
- [x] 1.2 Review `terraform/dashboards/home-assistant-house-overview.json` and `terraform/dashboards/home-assistant-environment.json` for reusable Home Assistant metric queries and panel conventions
- [x] 1.3 Confirm which exported Home Assistant temperature and humidity entities represent indoor and outdoor groups; document any ambiguous or missing outdoor entity coverage before building queries
  - Note: indoor averages reuse the curated Home Assistant house overview sensor group. Outdoor averages use `sensor.thermo_hygrometer_outside_shed_temperature` and `sensor.thermo_hygrometer_outside_shed_humidity`; these entities were added to the Home Assistant Prometheus export allowlist so they can be retained in Mimir. The office summary panel uses `sensor.thermo_hygrometer_office_temperature`, and the curated Home Assistant dashboard temperature/humidity groups now use `sensor.thermo_hygrometer_office_temperature` and `sensor.thermo_hygrometer_office_humidity` after the Office entity name drift from the old `sensor.indoor_outdoor_meter_f2f6_*` names.

## 2. Dashboard Implementation

- [x] 2.1 Add a House Environment row or section to `terraform/dashboards/platform-overview.json`
- [x] 2.2 Add average indoor temperature and average outdoor temperature panels backed by `mimir` Home Assistant metrics
- [x] 2.3 Add average indoor humidity and average outdoor humidity panels backed by `mimir` Home Assistant metrics
- [x] 2.4 Add CO2 and air-quality summary panels using numeric Home Assistant environmental telemetry such as CO2, PM2.5, and PM10 metrics
- [x] 2.5 Add or update dashboard links/text so operators can drill down to the existing Home Assistant environmental or house overview dashboards

## 3. Validation

- [x] 3.1 Validate `terraform/dashboards/platform-overview.json` is well-formed JSON after edits
- [x] 3.2 Run formatting or lint checks available for Terraform/dashboard assets without exposing secrets
- [x] 3.3 Run a targeted OpenTofu plan through `./scripts/tofu.sh` for the Grafana dashboard changes
- [x] 3.4 Verify the updated Operations Platform Overview renders the new panels with non-empty data or clearly labelled no-data behavior for unavailable outdoor/air-quality series

## 4. Repository Hygiene

- [x] 4.1 Confirm no secrets, tokens, state files, or generated sensitive artifacts were created or modified
- [x] 4.2 Stage the OpenSpec artifacts and implementation files required for commit
