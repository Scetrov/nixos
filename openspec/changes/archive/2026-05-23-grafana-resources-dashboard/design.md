# System Resource Monitoring Dashboard Technical Design

## Context

Our NixOS cluster comprises multiple nodes (`fyne`, `habiki`, and `bullit`) with resource telemetry shipped via Alloy and Mimir. Currently, there is no centralized, declarative resource monitoring dashboard in Grafana. To maintain reproducible IaC, we must configure and provision this dashboard declaratively in `grafana.nix`.

## Goals / Non-Goals

**Goals:**

- Provision a declarative system resource monitoring dashboard in `src/roles/nixos/files/etc/nixos/modules/grafana.nix`.
- Add a dynamic `$host` variable dropdown querying the `host` label from the `"mimir"` data source.
- Standardize resource visualization panels (CPU, Memory, Disk) using correct PromQL expressions isolated by `{host="$host"}`.

**Non-Goals:**

- Configuring external notification policies or alerts inside this dashboard (handled separately via Alerting/OnCall).
- Provisioning separate dashboards for individual machines (a single dynamic dashboard resolves this).

## Decisions

### 1. Dashboard Definition Structure

- **Option A (Recommended):** Define the dashboard structure as a Nix attribute set in `grafana.nix` and serialize it using `builtins.toJSON`.
  - *Rationale:* Keeps the module self-contained, eliminates multi-line JSON escaping inside Nix strings, and validates the dashboard structure statically during Nix evaluation.
- **Option B:** Commit a separate static JSON file to the repo and import it via Nix's `builtins.readFile`.
  - *Rationale:* Less elegant; requires tracking separate untyped files.

*Decision:* Option A.

### 2. Dashboard Provisioning Path

- **Option A (Recommended):** Use `services.grafana.provision.dashboards.settings` targeting `/etc/grafana/dashboards`, and symlink the JSON file into it via `systemd.tmpfiles.rules` from the Nix Store.
  - *Rationale:* Standard declarative dashboard provisioning in NixOS. Keeps the files read-only and immutable.
- **Option B:** Write the dashboard file imperatively using a script or Ansible task.
  - *Rationale:* Imperative configuration violates the automation and reproducibility goals of this repository.

*Decision:* Option A.

### 3. Dynamic Selection PromQL Queries

- **Option A (Recommended):** Implement `{host="$host"}` filtering across panels querying the `"mimir"` default Prometheus datasource.
  - *Rationale:* Isolates host metrics dynamically based on the selected machine in the `$host` template variable dropdown.
- **PromQL Metrics:**
  - **CPU:** `100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle", host="$host"}[5m])) * 100)`
  - **Memory:** `(node_memory_MemTotal_bytes{host="$host"} - node_memory_MemAvailable_bytes{host="$host"}) / node_memory_MemTotal_bytes{host="$host"} * 100`
  - **Disk:** `100 - (node_filesystem_free_bytes{fstype!="tmpfs", mountpoint="/", host="$host"} / node_filesystem_size_bytes{fstype!="tmpfs", mountpoint="/", host="$host"} * 100)`

*Decision:* Option A.

## Risks / Trade-offs

- **[Risk]** Datasource UID mismatch or offline mimir.  
  *Mitigation:* Use standard Mimir datasource UID `"mimir"` matching the configuration in `grafana.nix`.
- **[Risk]** Large dashboards can exceed Nix store memory limits if not minified.  
  *Mitigation:* Keep the dashboard panels simple, focused on core system resource metrics, and declare only required metadata fields.
