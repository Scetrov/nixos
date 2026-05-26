# Home Assistant Environmental Metrics Technical Design

## Context

Home Assistant already runs declaratively on `habiki`, and the broader observability stack on the same host already provides Prometheus, Mimir, Loki, and Grafana. Live Home Assistant data confirms that the runtime currently has environmental entities for temperature, humidity, CO2, PM2.5, PM10, and air-quality state, but the managed Home Assistant configuration does not yet enable the internal Prometheus exporter and the Home Assistant service dashboard still explicitly declares that metrics are not enabled.

This change crosses multiple repo boundaries:

- `home-assistant.nix` generates the managed runtime configuration.
- `prometheus.nix` provides the local scrape path and remote write into Mimir.
- Grafana service dashboards are source-controlled under `terraform/dashboards` and applied through OpenTofu.
- Secrets for runtime integrations are handled through age-backed files under `/root/secrets` and consumed declaratively by NixOS services.

Because the change spans runtime configuration, secret handling, scrape configuration, and dashboard provisioning, a written design is useful before implementation.

## Goals / Non-Goals

**Goals:**

- Enable Home Assistant's internal Prometheus exporter declaratively from the managed configuration.
- Restrict the exported entity set to environmental metrics that are already present and useful for dashboards.
- Scrape Home Assistant locally from Prometheus on `habiki` using a token-backed authenticated request rather than exposing an unauthenticated public metrics endpoint.
- Preserve the existing observability contract by labeling metrics with stable service identity and making them queryable through both Prometheus and Mimir.
- Upgrade the Home Assistant service dashboard from a placeholder into a real operational dashboard and add an environmental dashboard for time-series climate and air-quality views.

**Non-Goals:**

- Adding OpenTelemetry traces or profiles for Home Assistant in this change.
- Reworking Home Assistant automations, helpers, or Lovelace dashboards.
- Exporting every available Home Assistant entity or diagnostic sensor.
- Introducing public ingress for the metrics endpoint through Caddy.

## Decisions

### 1. Home Assistant metrics remain private and are scraped locally

- **Option A (Recommended):** Enable the Home Assistant Prometheus integration with authentication left on, and scrape `127.0.0.1:8123` locally from Prometheus using a long-lived access token.
  - *Rationale:* This matches the repo's existing pattern of local collection on `habiki`, avoids exposing Home Assistant metrics through public ingress, and keeps authentication under repo-managed secret handling.
- **Option B:** Disable authentication on the Home Assistant metrics endpoint.
  - *Rationale:* Simpler to wire, but weakens the security boundary around a Home Assistant API surface.
- **Option C:** Scrape through the public `homeassistant.net.scetrov.live` route.
  - *Rationale:* Unnecessary extra network hop and a worse failure domain when Prometheus already runs on the same host.

*Decision:* Option A.

### 2. The exporter configuration is managed in `home-assistant.nix`

- **Option A (Recommended):** Extend the generated `configuration.yaml` in `src/roles/nixos/files/etc/nixos/modules/home-assistant.nix` with a managed `prometheus:` block.
  - *Rationale:* The repository already treats that file as declarative source of truth for Home Assistant core configuration, including proxy trust and OIDC settings.
- **Option B:** Configure the Prometheus integration manually through the Home Assistant UI.
  - *Rationale:* Faster once, but breaks reproducibility and creates unmanaged drift.

*Decision:* Option A.

### 3. Export only the environmental entities that are already useful

- **Option A (Recommended):** Start with a curated include list containing the live Matter CO2, PM2.5, PM10, air-quality, temperature, and humidity sensors plus the current SwitchBot and Hue room temperature and humidity sensors.
  - *Rationale:* Keeps cardinality low, gives immediate dashboard value, and avoids turning on noisy diagnostics, firmware, battery, or Bluetooth RSSI metrics by default.
- **Option B:** Export every supported Home Assistant sensor entity.
  - *Rationale:* Broader coverage, but creates unnecessary noise and makes dashboard queries harder to stabilize.

*Decision:* Option A.

### 4. The Home Assistant scrape job stays close to the service module

- **Option A (Recommended):** Add the Home Assistant scrape job from `home-assistant.nix` using `services.prometheus.scrapeConfigs = lib.mkAfter [ ... ]`, following the same pattern used by other service modules.
  - *Rationale:* Keeps service ownership local and avoids turning `prometheus.nix` into a central registry for every application-specific scrape target.
- **Option B:** Add the scrape job directly to the base list in `prometheus.nix`.
  - *Rationale:* Centralized, but less maintainable as service count grows.

*Decision:* Option A.

### 5. Dashboards are split into service-health and environmental views

- **Option A (Recommended):** Rework `home-assistant-service.json` into an operational dashboard for scrape health and logs, and add a second dashboard focused on environmental telemetry.
  - *Rationale:* Service health and room telemetry serve different operator questions. Separating them keeps the service dashboard usable while still providing a richer environmental view.
- **Option B:** Put all operational and environmental panels on one dashboard.
  - *Rationale:* Fewer files, but the dashboard becomes cluttered and less readable.

*Decision:* Option A.

### 6. Use Prometheus for scrape health and Mimir for retained environmental history

- **Option A (Recommended):** Query target health and scrape internals from datasource `prometheus`, and query room and air-quality telemetry from datasource `mimir`.
  - *Rationale:* Prometheus is the authoritative source for live scrape state, while Mimir is the retained metrics backend already used for broader operational dashboards.
- **Option B:** Point all panels at Prometheus only.
  - *Rationale:* Simpler initially, but loses the repo's standard long-term metrics path.

*Decision:* Option A.

## Risks / Trade-offs

- **[Risk]** Home Assistant Prometheus metric names and labels may not match the ideal dashboard shape on the first pass.  
  *Mitigation:* Start with a curated exporter config, validate the actual exported series, and only add recording rules later if query ergonomics remain poor.
- **[Risk]** A manually created long-lived Home Assistant token can drift or expire operationally if not documented.  
  *Mitigation:* Store it as an age-backed secret, document the creation and rotation workflow, and keep only the file path in repo-managed config.
- **[Risk]** Exporting too many Home Assistant entities can increase scrape volume and cardinality.  
  *Mitigation:* Use an explicit include list and skip diagnostics, battery, firmware, and RSSI entities in the initial rollout.
- **[Risk]** Dashboard provisioning can succeed while metrics are still absent, leaving confusing empty panels.  
  *Mitigation:* Sequence the rollout so NixOS deploy and scrape validation happen before the OpenTofu dashboard apply.

## Migration Plan

1. Create a Home Assistant long-lived access token dedicated to Prometheus scraping.
2. Add the age-backed secret and wire it into the NixOS configuration.
3. Extend Home Assistant's managed `configuration.yaml` with the Prometheus integration and curated entity filters.
4. Add the local Prometheus scrape job and deploy the NixOS changes to `habiki`.
5. Validate the Home Assistant metrics endpoint locally, confirm the Prometheus target is up, and confirm the new series are queryable in both Prometheus and Mimir.
6. Update the Home Assistant service dashboard and add the environmental dashboard in Terraform-managed Grafana JSON.
7. Apply the Grafana changes through `./scripts/tofu.sh` and verify the dashboards render real environmental telemetry.

Rollback is straightforward: remove the Home Assistant `prometheus:` block, remove the scrape job, deploy the NixOS rollback, and then revert or remove the dashboard panels that depend on those metrics.

## Open Questions

- Whether the initial dashboard should include the enum `air_quality` sensors or treat them as optional status-only panels because the numeric CO2 and particulate metrics already carry most of the useful signal.
- Whether the first implementation should add Home Assistant-specific recording rules for friendlier query names, or defer that until the raw exported series are inspected after rollout.
