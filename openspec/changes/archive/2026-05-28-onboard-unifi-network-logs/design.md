## Context

The repository already runs the central observability stack on `habiki`, with Loki for log storage, Grafana for dashboards, and Alloy for host-local logs and metrics. That path works well for systemd journals and local service logs, but it does not currently ingest UniFi Network remote syslog from the UCG Ultra at `10.229.0.1`. Operators therefore have to inspect UniFi directly when debugging firewall drops, IDS/threat events, or warning/error conditions.

This change adds a dedicated remote logging path for UniFi network events while preserving the current Alloy-based telemetry path for local host services. The implementation must stay declarative, avoid hardcoded secrets, keep the exposure tightly scoped to the UCG Ultra, and fit the existing Grafana operations portal conventions.

## Goals / Non-Goals

**Goals:**
- Ingest UniFi Network remote syslog from the UCG Ultra into Loki through a dedicated, declarative pipeline on `habiki`.
- Restrict the receiver to the UCG Ultra source address and a custom UDP port.
- Parse and retain only firewall events, threat/IDS events, and warning-or-higher non-firewall events.
- Normalize retained events into stable labels and structured JSON fields that support Grafana log queries and dashboard panels.
- Add a declaratively managed Grafana dashboard and service-catalog entry for UniFi network log visibility.
- Document the UniFi Network Application remote logging configuration required to point the UCG Ultra at `habiki`.

**Non-Goals:**
- Replace Alloy for existing host-local log collection.
- Add GeoIP or country-map enrichment.
- Rebuild the Loki or Grafana deployment model.
- Introduce manual-only Grafana dashboard ownership.
- Expand this change into broader UniFi metrics scraping or SNMP collection.

## Decisions

### 1. Use a dedicated Vector receiver for UniFi remote syslog
- **Decision:** Introduce a separate NixOS module that runs Vector as the UniFi-specific syslog receiver and parser.
- **Rationale:** The proposal explicitly keeps the Alloy path unchanged. A dedicated Vector service isolates remote syslog parsing concerns from the existing journal and file-log pipeline and matches the need for event filtering and structured remapping.
- **Alternative considered:** Extend Alloy to receive and parse remote syslog. This keeps one agent, but it increases risk to the existing local telemetry path and is less ergonomic for the required filtering and remap logic.

### 2. Bind the receiver on `habiki` to UDP port `5514` and restrict the firewall to `10.229.0.1`
- **Decision:** Listen on a custom UDP syslog port (`5514`) and add explicit firewall allow/deny behavior so only the UCG Ultra source IP can send to that port.
- **Rationale:** `5514` is a conventional non-privileged alternative to default syslog and avoids interfering with any future standard syslog usage on port `514`. Source restriction reduces blast radius and aligns with the proposal requirement that only the UCG Ultra may reach the receiver.
- **Alternative considered:** Reuse UDP `514`. That is more familiar, but it is a shared default that increases collision risk and makes future coexistence with other syslog senders harder.

### 3. Keep only high-signal UniFi events before Loki ingestion
- **Decision:** Filter the stream inside Vector so the retained set is limited to firewall events, threat/IDS events, and warning-or-higher non-firewall events.
- **Rationale:** The UCG Ultra can emit a large amount of low-value connection chatter. Filtering before push keeps Loki retention focused on actionable network and security events while preserving the existing 7-day retention budget.
- **Alternative considered:** Ingest all UniFi syslog and filter only in dashboards. That is simpler to start, but it increases storage noise and makes queries slower and less predictable.

### 4. Normalize retained events into a stable `service` and `host` identity plus searchable fields
- **Decision:** Push UniFi events to Loki with stable labels including `service="unifi-network"` and `host="ucg-ultra"`, and emit structured fields for event class, action, source and destination IPs, ports, protocol, interface, rule context, severity, and threat metadata when present.
- **Rationale:** The Grafana operations portal relies on consistent service identity across signals. Although these are remote device logs collected on `habiki`, the operational subject is the UCG Ultra network edge, not the collector host.
- **Alternative considered:** Label the logs primarily as `host="habiki"` because the receiver runs there. That would obscure the originating network device and make the dashboard less intuitive for operators.

### 5. Manage the dashboard through the existing Terraform-based Grafana workflow
- **Decision:** Add the UniFi dashboard JSON under `terraform/dashboards/`, register it in `terraform/grafana.tf`, and surface it from the service catalog.
- **Rationale:** Existing portal dashboards are source-controlled and provisioned through OpenTofu. Reusing that workflow keeps review and deployment consistent.
- **Alternative considered:** Build the dashboard directly in the Grafana UI and export it later. That is faster during experimentation but does not satisfy the repository’s declarative ownership rule.

### 6. Document operator setup in a dedicated UniFi logging guide
- **Decision:** Add repository documentation that describes the UniFi Network Application remote logging settings, expected host/port/protocol values, and post-deploy validation steps.
- **Rationale:** This change depends on an external controller setting. Without explicit operator guidance, the repo changes alone would not complete the feature.
- **Alternative considered:** Embed setup notes only in the OpenSpec proposal or tasks. That would make long-term operations harder because the instructions would not live with the operational docs.

## Risks / Trade-offs

- **[Risk] UniFi syslog formats vary by event type or firmware version** → Mitigation: structure the parser to keep raw message context for unmatched fields and validate against representative firewall and threat samples before rollout.
- **[Risk] UDP syslog can drop bursts under load** → Mitigation: limit scope to high-signal retained events and keep the receiver local on the same LAN as the UCG Ultra.
- **[Risk] Over-filtering hides useful incidents** → Mitigation: keep firewall and threat categories unconditionally, and retain warning-or-higher events outside those categories.
- **[Risk] Source restriction drifts from the actual gateway IP** → Mitigation: document the expected UCG Ultra address and keep the allow rule isolated to a configurable module option if the device address changes later.
- **[Risk] Dashboard queries depend on label choices that differ from the existing service catalog wording** → Mitigation: standardize on `service="unifi-network"` and `host="ucg-ultra"` across the dashboard JSON, docs, and spec artifacts.

## Migration Plan

1. Add the UniFi-specific Vector module and enable it on `habiki`.
2. Open the custom UDP syslog port only for `10.229.0.1` and route retained logs to local Loki.
3. Add the UniFi dashboard JSON and Terraform dashboard resource, then update the service catalog entry.
4. Add operator documentation for the UniFi Network Application remote logging settings.
5. Validate Nix syntax, OpenSpec artifacts, and dashboard registration locally.
6. Deploy narrowly with `./scripts/play.sh --limit habiki --tags nixos` and the Terraform/Grafana workflow, then confirm logs and dashboard queries in Grafana.

Rollback is to disable the UniFi receiver module, remove the dashboard registration, redeploy the targeted workflows, and remove the remote logging target from the UniFi controller.

## Open Questions

- Which concrete UniFi syslog message variants are emitted by the current UCG Ultra firmware for firewall allow, firewall block, and threat/IDS events?
- Should the initial dashboard emphasize log volume trends or recent-event tables first if representative sample data is limited during authoring?
- Do we want the receiver port and source IP modeled as module options immediately, or keep them fixed in this change and generalize only if a second network device is onboarded later?
