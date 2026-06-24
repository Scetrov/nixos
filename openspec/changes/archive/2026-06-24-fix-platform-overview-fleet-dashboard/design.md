## Context

`terraform/dashboards/platform-overview.json` provisions the Operations Platform Overview dashboard in Grafana. The dashboard currently has two rows: Observability Stack Health and Fleet Health. The top row has five four-column stat panels on a 24-column grid, leaving one empty four-column space. The `Hosts Reporting` panel currently evaluates `count(count by (host) (up{job="node"} == 1))`, but live Mimir telemetry shows fleet node metrics are reported under `job="integrations/unix"` with `host` labels for `fyne`, `habiki`, and `bullit`. The stale/local `job="node"` target does not represent the active fleet and causes the stat to show no data.

The existing `terraform/dashboards/system-resources.json` dashboard already contains working node-exporter PromQL for disk, filesystem, network, process, and CPU/memory signals. This change should reuse those metric families and adapt them to fleet-level grouping by `host` rather than per-host filtering by `$host`.

## Goals / Non-Goals

**Goals:**

- Restore accurate fleet host reporting on the Operations Platform Overview dashboard.
- Fill the unused top-row grid slot with a useful observability stack health stat.
- Expand the Fleet Health section beyond CPU and memory to include host-level storage, disk queue/busy pressure, disk throughput/IOPS, and network error/drop visibility.
- Keep panels fleet-scoped with `by (host)` or `by (host, device)` grouping where useful.
- Use the Mimir datasource UID `mimir` consistently.
- Validate changed PromQL against live Grafana/Mimir before sign-off.

**Non-Goals:**

- Adding alert rules or notification policies.
- Adding per-service troubleshooting panels.
- Reworking the separate System Resources dashboard.
- Implementing expected-vs-actual inventory reconciliation.
- Implementing NixOS generation drift detection or deployment-ring tracking.

## Decisions

### Use active Alloy/node-exporter scrape health for `Hosts Reporting`

Use active fleet telemetry rather than the stale local `job="node"` scrape. The primary query should be:

```promql
count(count by (host) (up{job="integrations/unix"} == 1))
```

Rationale: this directly measures hosts currently reporting through the active Unix integration path. `node_uname_info` is also available and returns the same fleet cardinality, but `up` is the clearest scrape-health signal for a reporting-host stat.

Alternative considered: keep `job="node"`. Rejected because it only reflects the old local node scrape and does not match the active fleet labels.

### Fill the top-row gap with Prometheus health

Add a sixth four-column stat panel for Prometheus health so the Observability Stack Health row fully occupies the 24-column grid:

```promql
max(up{job="prometheus"})
```

Rationale: Prometheus is the scrape and remote-write source feeding Mimir for many metrics. Its health belongs beside Grafana, Mimir, Loki, and Tempo.

Alternative considered: add Alloy health instead. Alloy is also useful, but Prometheus health gives broader signal for the current dashboard's metrics path and fills the immediate observability stack row cleanly.

### Promote fleet-level resource pressure panels from System Resources patterns

Adapt existing node-exporter PromQL from `system-resources.json` into fleet-level panels:

- Root disk used by host using `node_filesystem_avail_bytes` / `node_filesystem_size_bytes` grouped by `host`.
- Disk throughput by host/device using `node_disk_read_bytes_total` and `node_disk_written_bytes_total`.
- Disk IOPS by host/device using completed read/write counters.
- Disk busy time or average queue depth by host/device using `node_disk_io_time_seconds_total` and `node_disk_io_time_weighted_seconds_total`.
- Network errors/drops by host/device using receive/transmit error and drop counters.

Rationale: these are standard node-exporter fleet operations signals and are already present in live Mimir.

Alternative considered: embed the entire System Resources dashboard. Rejected because the Platform Overview should remain a concise cockpit, not a full per-host deep-dive.

### Preserve dashboard-first scope

This change intentionally improves visibility only. It does not create alerts, runbooks, inventory reconciliation, or deployment governance. Those can follow once the fleet cockpit shows the core signals reliably.

## Risks / Trade-offs

- Metric labels differ between hosts or exporters → Validate each query against live Mimir and prefer metric families already observed in production.
- Too many device-level series make panels noisy → Use legends that include `host` and `device`; aggregate by host only where device detail is not useful.
- Dashboard becomes too dense → Keep the platform overview to high-signal fleet panels and leave detailed host investigation to System Resources.
- `up{job="integrations/unix"}` semantics depend on Alloy integration naming → Document this choice in the spec and validate before deployment.
- Terraform/OpenTofu dashboard provisioning may overwrite manual Grafana edits → Make all changes declaratively in `terraform/dashboards/platform-overview.json` and deploy through the existing wrapper.

## Migration Plan

1. Update `terraform/dashboards/platform-overview.json` declaratively.
2. Validate JSON syntax locally.
3. Validate all changed PromQL expressions against Grafana's Mimir datasource.
4. Deploy using the existing secure OpenTofu wrapper and targeted orchestration where applicable.
5. Verify the dashboard renders with no no-data fleet panels under normal host-reporting conditions.

Rollback is to revert the dashboard JSON change and re-apply the Grafana dashboard resource.

## Open Questions

- Should the top-row sixth stat be Prometheus health or Alloy health? The proposed default is Prometheus.
- Should disk queue/busy panels aggregate by host for readability or preserve host/device detail for diagnosis? The proposed default is host/device detail with concise legends.
