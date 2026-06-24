## Context

The Operations Platform Overview (`terraform/dashboards/platform-overview.json`) is the Grafana landing dashboard for platform and fleet health. Home Assistant environmental telemetry is already exported through the managed Prometheus integration, retained in the `mimir` datasource, and used by the existing Home Assistant environmental and house overview dashboards.

This change adds house-level climate and air-quality summaries directly to the platform landing page. The implementation should reuse the existing declarative Grafana JSON workflow and the established Home Assistant query patterns rather than adding new collectors, routes, secrets, or Grafana resources.

## Goals / Non-Goals

**Goals:**

- Add a clearly labelled House Environment section to the Operations Platform Overview dashboard.
- Show average indoor and average outdoor temperature from Home Assistant telemetry where the exported entity allowlist supports those groups.
- Show average indoor and average outdoor humidity from Home Assistant telemetry where the exported entity allowlist supports those groups.
- Show CO2 and air-quality panels using the existing CO2 and particulate/air-quality metrics already exported for Home Assistant.
- Keep panels backed by the `mimir` datasource and source-controlled dashboard JSON.
- Preserve existing platform overview panels and links.

**Non-Goals:**

- Do not add a new Grafana dashboard; this updates the existing platform overview.
- Do not change Home Assistant entity exports unless implementation confirms outdoor metrics are missing from the current allowlist and the missing entities are known.
- Do not add alerts, notification policies, external dependencies, new secrets, or new ports.
- Do not replace the more detailed Home Assistant environmental or house overview dashboards.

## Decisions

- Reuse existing Home Assistant metric names and datasource path.
  - Use `homeassistant_sensor_temperature_celsius`, `homeassistant_sensor_humidity_percent`, `homeassistant_sensor_carbon_dioxide_ppm`, and the available PM/air-quality metric series through the `mimir` datasource with `job="home-assistant"` and `service="home-assistant"` filters.
  - Rationale: this matches the retained telemetry path already proven by Home Assistant dashboards.
  - Alternative considered: query local Prometheus scrape data. This would make the platform overview less consistent with the retained historical dashboards and may reduce available history.

- Add a compact landing-page section rather than duplicating the full Home Assistant dashboards.
  - Use stat panels for current averages and concise trend panels where useful for CO2 and air-quality context.
  - Rationale: the platform overview should remain a landing page and link users to detailed dashboards for deeper inspection.
  - Alternative considered: embed all Home Assistant environmental panels. This would make the platform overview too large and duplicate the service dashboard.

- Treat indoor/outdoor grouping as explicit query allowlists.
  - Indoor averages should reuse the current curated indoor entity group from `home-assistant-house-overview.json`.
  - Outdoor averages should use known outdoor Home Assistant temperature/humidity entities if they are already exported; if the current exported entities cannot be confidently classified as outdoor, implementation should add placeholders only if clearly labelled, or update the Home Assistant allowlist in a separate follow-up once the correct entities are identified.
  - Rationale: averages are only useful when sensors are intentionally grouped; a regex over all `indoor_outdoor_meter_*` entities could produce misleading data.
  - Alternative considered: average every temperature/humidity sensor. This hides indoor/outdoor distinctions requested by the operator.

- Keep Terraform provisioning unchanged unless registration is already present.
  - `platform-overview.json` is already registered by `grafana_dashboard.platform_overview`, so implementation should not need `terraform/grafana.tf` changes.
  - Rationale: minimizing IaC surface area reduces deployment risk.

## Risks / Trade-offs

- Outdoor entity classification may be ambiguous → Verify exported Home Assistant entities before finalizing outdoor queries; keep labels honest and avoid inventing groups.
- Additional panels can crowd the landing page → Use a compact row and preserve existing platform/fleet sections.
- Grafana JSON can be easy to break by hand edits → Validate with JSON tooling and a targeted OpenTofu plan through `./scripts/tofu.sh`.
- Air-quality entity metrics may not expose numeric values consistently → Prefer known numeric CO2 and particulate metrics already used by Home Assistant environmental dashboards; document any missing air-quality metric as a limitation in panel text if needed.
