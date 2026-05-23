# System Resource Monitoring Tasks

## 1. Grafana Declarative Provisioning

- [x] 1.1 Add `provision.dashboards.settings` config under `services.grafana` in `src/roles/nixos/files/etc/nixos/modules/grafana.nix`
- [x] 1.2 Define the dashboard JSON structure as a Nix attribute set inside `grafana.nix` with CPU, Memory, and Disk panels
- [x] 1.3 Configure the `$host` template variable dropdown in the dashboard attribute set querying the `host` label from `mimir`
- [x] 1.4 Add a `systemd.tmpfiles.rules` symlink entry to write the serialized dashboard JSON to `/etc/grafana/dashboards/system-resources.json`

## 2. Static Verification

- [x] 2.1 Validate Nix formatting or syntax using the repository's established checks for changed Nix files
- [x] 2.2 Confirm no secrets, tokens, keys, connection strings, or generated state files were added
- [x] 2.3 Stage all required files for commit after verification

## 3. Deploy-Time Verification

- [x] 3.1 Deploy narrowly to `habiki` using a targeted command such as `./scripts/play.sh --limit habiki --tags nixos`
- [x] 3.2 Verify the `grafana` systemd service is active and running cleanly on `habiki`
- [x] 3.3 Access the Grafana UI and verify the "System Resources" dashboard is visible in the dashboards list
- [x] 3.4 Verify the `$host` template variable dropdown is populated with unique machine names (`fyne`, `habiki`, `bullit`)
- [x] 3.5 Verify the CPU, Memory, and Disk panels successfully display metric lines isolated for the selected host without syntax errors
