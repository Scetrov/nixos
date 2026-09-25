## 1. Verify telemetry contract

- [x] 1.1 Query the managed Prometheus datasource to verify resettable event totals, stable player identity labels, and available health, days-alive, and zombies-killed series.
- [x] 1.2 Record unsupported player fields as unavailable behavior and confirm that no query infers missing samples as zero.

## 2. Update dashboard visualizations

- [x] 2.1 Replace the `Events / rolling hour` panel in `terraform/dashboards/project-zomboid-service.json` with interval-aligned, reset-aware event count bars using Grafana’s adaptive interval and a readable minimum interval.
- [x] 2.2 Update the event panel title, legend, description, colors, and no-data behavior to communicate events per interval and unavailable telemetry.
- [x] 2.3 Replace the online-only roster instant query with range queries and Grafana transformations that retain every observed player and reduce each player’s fields to the latest observation and last-seen timestamp.
- [x] 2.4 Add the verified latest health, days alive, and zombies killed fields to the roster, or render each unsupported field as unavailable without fabrication.
- [x] 2.5 Update roster labels and description to state dashboard-timeframe scope and preserve compatible player selector/path behavior.

## 3. Validate and provision

- [x] 3.1 Validate the dashboard JSON and declarative Grafana provisioning configuration.
- [x] 3.2 Render or inspect the dashboard for short, normal, and long time ranges to confirm readable interval bars, reset handling, and no-data behavior.
- [x] 3.3 Verify a player disconnected before the range end remains in the roster with the correct last-seen time and latest supported status values.
- [x] 3.4 Deploy through the targeted existing automation path and confirm the provisioned dashboard matches the versioned JSON.
