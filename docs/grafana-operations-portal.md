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

- `frontier-indexer`: metrics and logs available now; traces and profiles are not yet present. The service dashboard includes a Loki-backed database setup failure stat; this should remain at `0` once the preflight remediation is deployed.
- `dependency-track`: metrics and logs available after Prometheus scrape onboarding; traces and profiles are not yet present.
- `oncall`: logs available now; metrics exporter, traces, and profiles are not yet present.
- `hermes`: logs and external UI available now; metrics, traces, and profiles are not yet present.
- `home-assistant`: logs and authenticated local metrics collection are configured, with retained environmental history in Mimir; see [the service runbook](home-assistant.md). Traces still require independent integration/verification.

## Dashboard semantics and validation

System Resources is now owned by `terraform/grafana.tf` and
`terraform/dashboards/system-resources.json`, not embedded Nix dashboard JSON.
The Grafana module removes the legacy file to avoid duplicate provisioning.
Use Mimir UID `mimir`, derive the `host` dropdown from real host labels, and
filter CPU/memory/disk queries by the selected host rather than instance aliases.
Old acceptance tasks checking for `/etc/grafana/dashboards/system-resources.json`
are superseded by this ownership change; they are not outstanding deployment work.

Platform Hosts Reporting uses active Unix integration scrapes:

```promql
count(count by (host) (up{job="integrations/unix"} == 1))
```

The full-width stack-health row includes Prometheus. Fleet pressure views cover
root filesystem space, throughput/IOPS, disk busy/queue and network errors/drops
with meaningful host/device legends. They are concise drilldown entry points,
not host-wide values mislabelled as application consumption.

House panels use retained Home Assistant environmental metrics and reviewed
indoor/outdoor allowlists, not every similarly named sensor. GitHub risk views
distinguish zero findings from unavailable/forbidden/disabled coverage and link
to the repository drilldown. AI quota cards follow the
[freshness/window contract](codex-app-server.md#exporter-and-dashboard-contract).
Project Zomboid is registered in Operations / Services and the service catalog.

Validate JSON and real datasource queries, selected-host isolation, catalog
links and available signal drilldowns before applying through `scripts/tofu.sh`.
For missing traces/profiles, show the gap rather than fabricating coverage.
Dashboard rollback restores source and reapplies through the wrapper; persistent
Mimir/Loki history is not deleted. The old declarative resource-dashboard archive
had four unchecked rollout checks; validate the current OpenTofu-owned dashboard
when changing it rather than treating old checkboxes as proof of live acceptance.

Investigations group recurring logs by source/message, rank actual service
failure above accepted noise, and record the reason and revisit condition for a
deferral. After remediation, verify service health, the original symptom in recent
logs, and its real telemetry path. A passing readiness probe alone is not proof
of authenticated database access or successful application setup.

## Reviewed Noise And Remediation Decisions

### Frontier Indexer database setup failures

- **Status:** active remediation.
- **Affected host/unit:** `habiki`, `podman-frontier-indexer.service`.
- **Decision:** the service now has a declarative database preflight before container startup. The preflight validates the runtime env file, database password file, Podman-network connectivity, and authenticated PostgreSQL access before `podman-frontier-indexer.service` starts.
- **Operator signal:** use the Frontier Indexer service dashboard's `Database Setup Failures (15m)` stat and recent logs panel. Any non-zero value after deployment is an active failure, not accepted noise.

### PCIe AER correctable errors

- **Status:** reviewed, accepted as host-specific hardware/link noise for now.
- **Affected host/device:** `habiki`, root port `0000:00:1c.0` (`8086:9d15`) with child `0000:01:00.0` Intel Wireless 3165 (`8086:3165`).
- **Decision:** no boot mitigation is applied in this change. The events are correctable Physical Layer `RxErr` messages with no fatal or non-fatal AER counters observed. Avoid fleet-wide `pci=noaer` because it would hide future hardware faults.
- **Revisit condition:** apply a host-specific, reversible boot mitigation only if the errors correlate with device malfunction, suspend/resume instability, or alert fatigue that cannot be addressed in dashboard/query treatment. Roll back by removing the host-specific kernel parameter and rebuilding `habiki`.

### Grafana resource-client warnings

- **Status:** reviewed, accepted as benign Grafana/plugin resource-client noise for now.
- **Affected host/unit:** `habiki`, `grafana.service`.
- **Observed identity:** `subject=user:4 uid=user:bfm92pytdb56od`.
- **Decision:** no log suppression is applied in this change. The warnings do not indicate a failing managed service and are ranked below Frontier Indexer startup failures. Keep them visible in raw logs but separate them from unresolved service failures in operations notes.
- **Revisit condition:** investigate a declarative Grafana/plugin update or configuration fix if the warning volume increases materially, maps to a broken plugin feature, or starts affecting alert quality.
