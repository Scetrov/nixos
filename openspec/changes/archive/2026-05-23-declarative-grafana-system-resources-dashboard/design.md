# Declarative Grafana System Resources Dashboard

## Context

Grafana is managed in `src/roles/nixos/files/etc/nixos/modules/grafana.nix` with declarative datasources and dashboard providers. The default Prometheus-compatible datasource is Mimir with UID `mimir`, and Alloy/node-exporter telemetry uses a `host` label that distinguishes machines such as `fyne`, `habiki`, and `bullit`.

The current module already follows the desired pattern by defining a `dashboardJson` value and exposing it through `/etc/grafana/dashboards/system-resources.json`. This change formalizes that behavior and closes gaps around dynamic host filtering and verification.

## Goals / Non-Goals

**Goals:**

- Provision the dashboard entirely through NixOS and the existing Ansible deployment workflow.
- Query host options dynamically from Mimir using the `host` label.
- Filter every CPU, memory, and disk panel with `{host="$host"}`.
- Keep the dashboard portable across the three target machines without hardcoding a fixed host list.

**Non-Goals:**

- Add a new datasource, metrics pipeline, or Alloy configuration.
- Add alert rules or notification policies.
- Replace Grafana provisioning with manual UI-managed dashboards.
- Add per-service panels beyond CPU, memory, and disk.

## Decisions

- Define dashboard JSON in `grafana.nix` using Nix attribute sets and `builtins.toJSON`.
  - Rationale: this keeps dashboard provisioning atomic with the rest of the Grafana module and avoids hand-maintained JSON drift.
  - Alternative considered: store a standalone JSON file. That is easier to copy from Grafana, but less consistent with the current module-local dashboard pattern.

- Use datasource UID `mimir` for the template variable and all panel targets.
  - Rationale: Mimir is the default long-term Prometheus-compatible datasource and already has UID `mimir`.
  - Alternative considered: use the Prometheus datasource UID `prometheus`; this would not satisfy the requirement to use the default Prometheus/Mimir datasource.

- Use `label_values(host)` for the `$host` variable.
  - Rationale: it derives available hosts from the actual telemetry labels emitted by Alloy instead of duplicating host inventory in dashboard JSON.
  - Alternative considered: hardcode `fyne`, `habiki`, and `bullit`; this would require dashboard edits when hosts change.

- Apply `{host="$host"}` in every panel expression.
  - Rationale: the selected host must be the primary isolation boundary for all displayed metrics.
  - Alternative considered: filter by `instance`; Alloy target addresses can vary, while `host` is the intended logical label.

## Risks / Trade-offs

- Missing `host` labels in metrics -> The dropdown will be empty or panels will show no data. Mitigate by validating Mimir label values after deployment.
- Metric name changes from node-exporter -> Panels may show no data. Mitigate by verifying `node_cpu_seconds_total`, `node_memory_*`, and `node_filesystem_*` are present before sign-off.
- Dashboard edits in the Grafana UI may be overwritten -> Keep the dashboard source of truth in `grafana.nix` and avoid UI edits for this dashboard.

## Migration Plan

1. Update `src/roles/nixos/files/etc/nixos/modules/grafana.nix`.
2. Parse-check the Nix module.
3. Deploy with `./scripts/play.sh --limit habiki --tags nixos`.
4. Verify `/etc/grafana/dashboards/system-resources.json` exists on `habiki`.
5. Verify Mimir returns host labels for `fyne`, `habiki`, and `bullit`.
6. Verify Grafana loads the dashboard and the panels query with `{host="$host"}`.

Rollback is to revert the dashboard JSON and redeploy the same targeted NixOS workflow.

## Open Questions

- Should this dashboard later include network, load average, or filesystem inode panels?
- Should alert rules be added in a separate change after dashboard behavior is stable?
