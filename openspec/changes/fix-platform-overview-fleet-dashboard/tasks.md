## 1. Inspect Existing Dashboard and Metrics

- [x] 1.1 Review `terraform/dashboards/platform-overview.json` panel IDs, grid positions, datasource references, thresholds, and existing query style.
- [x] 1.2 Review `terraform/dashboards/system-resources.json` for reusable filesystem, disk, and network PromQL patterns.
- [x] 1.3 Query the Grafana Mimir datasource to confirm the active host reporting job, host labels, and required node metric families are present.

## 2. Update Observability Stack Health Row

- [x] 2.1 Change the `Hosts Reporting` panel query to count active fleet hosts from `up{job="integrations/unix"}` grouped by `host`.
- [x] 2.2 Add a sixth four-column observability stack stat panel for Prometheus health using the Mimir datasource.
- [x] 2.3 Adjust top-row grid positions so the Observability Stack Health row fills the full 24-column Grafana grid without empty space.

## 3. Expand Fleet Health Panels

- [x] 3.1 Add or update a fleet-level root disk utilization panel grouped by host.
- [x] 3.2 Add a fleet-level disk throughput panel grouped by host and device.
- [x] 3.3 Add a fleet-level disk IOPS panel grouped by host and device.
- [x] 3.4 Add a fleet-level disk busy-time or average queue-depth pressure panel grouped by host and device.
- [x] 3.5 Add a fleet-level network errors or drops panel grouped by host and device.
- [x] 3.6 Arrange Fleet Health panels into a readable 24-column layout that remains dashboard-first rather than per-host deep-dive focused.

## 4. Validate Dashboard Definition

- [x] 4.1 Validate `terraform/dashboards/platform-overview.json` is well-formed JSON.
- [x] 4.2 Validate each changed or added PromQL expression against Grafana's Mimir datasource.
- [x] 4.3 Confirm `Hosts Reporting` returns the active fleet count when `fyne`, `habiki`, and `bullit` are reporting.
- [x] 4.4 Confirm storage, disk, and network panels return data from live Mimir under normal fleet telemetry conditions.

## 5. Deployment Readiness

- [x] 5.1 Run a formatting or consistency check for the Terraform dashboard files if available.
- [x] 5.2 Review the diff for accidental secrets, tokens, or unrelated dashboard changes.
- [x] 5.3 Document the targeted deployment command to apply the Grafana dashboard through the existing secure OpenTofu/Ansible workflow.\n  - Command: `cd terraform && tofu apply -target=grafana_dashboard.platform_overview` (credentials and backend are injected by `scripts/tofu.sh`; for a minimal blast-radius run, source its exports or run the wrapper and then target the dashboard resource).
