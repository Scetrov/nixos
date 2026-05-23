# Declarative Grafana System Resources Dashboard

## 1. Dashboard Definition

- [x] 1.1 Review `src/roles/nixos/files/etc/nixos/modules/grafana.nix` for the existing `dashboardJson` structure and dashboard provider configuration
- [x] 1.2 Ensure the dashboard has UID `system-resources`, title `System Resources`, and is rendered from Nix via `builtins.toJSON`
- [x] 1.3 Ensure `/etc/grafana/dashboards/system-resources.json` is provisioned through `systemd.tmpfiles.rules`

## 2. Host Template Variable

- [x] 2.1 Configure the dashboard template variable with `name = "host"`
- [x] 2.2 Set the variable datasource to Prometheus/Mimir with `uid = "mimir"`
- [x] 2.3 Set the variable query to dynamically return unique `host` label values
- [x] 2.4 Confirm the variable is not a hardcoded list of `fyne`, `habiki`, and `bullit`

## 3. Resource Panels

- [x] 3.1 Configure the CPU utilization panel with a PromQL expression filtered by `{host="$host"}`
- [x] 3.2 Configure the memory usage panel with PromQL expressions filtered by `{host="$host"}`
- [x] 3.3 Configure the root disk utilization panel with PromQL expressions filtered by `{host="$host"}`
- [x] 3.4 Ensure all panel targets use datasource UID `mimir`

## 4. Validation

- [x] 4.1 Run `nix-instantiate --parse src/roles/nixos/files/etc/nixos/modules/grafana.nix`
- [x] 4.2 Run `openspec validate declarative-grafana-system-resources-dashboard --strict`
- [ ] 4.3 Deploy with `./scripts/play.sh --limit habiki --tags nixos`
- [ ] 4.4 Verify `/etc/grafana/dashboards/system-resources.json` exists on `habiki`
- [ ] 4.5 Verify Mimir exposes `host` label values for `fyne`, `habiki`, and `bullit`
- [ ] 4.6 Verify the Grafana dashboard loads and each CPU, memory, and disk panel includes `{host="$host"}` in its PromQL query
