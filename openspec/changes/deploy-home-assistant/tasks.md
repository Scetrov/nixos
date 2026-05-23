# Home Assistant Deployment Tasks

## 1. NixOS Service Module

- [ ] 1.1 Create `src/roles/nixos/files/etc/nixos/modules/home-assistant.nix` with `options.scetrov.services.home-assistant.enable = lib.mkEnableOption "Home Assistant service";`
- [ ] 1.2 Gate all Home Assistant declarations with `lib.mkIf config.scetrov.services.home-assistant.enable`
- [ ] 1.3 Declare `virtualisation.oci-containers.containers.homeassistant` using `ghcr.io/home-assistant/home-assistant:stable`
- [ ] 1.4 Configure `/var/lib/homeassistant:/config`, `TZ = "Europe/London"`, and `extraOptions = [ "--network=host" ]`
- [ ] 1.5 Add a `systemd.tmpfiles.rules` entry for `/var/lib/homeassistant` with mode `0755` and ownership `root root`
- [ ] 1.6 Allow inbound UDP firewall ports `1900` and `5353` only while the Home Assistant module is enabled
- [ ] 1.7 Add a comment or markdown reminder for the required Home Assistant `http.use_x_forwarded_for` and `trusted_proxies` YAML

## 2. Habiki Assignment

- [ ] 2.1 Add `./modules/home-assistant.nix` to the `imports` list in `src/roles/nixos/files/device-configuration/habiki.nix`
- [ ] 2.2 Set `scetrov.services.home-assistant.enable = true;` in `habiki.nix`

## 3. Caddy and Authentik Ingress

- [ ] 3.1 Add `virtualHosts."homeassistant.net.scetrov.live"` inside the `services.caddy` block in `src/roles/nixos/files/etc/nixos/modules/caddy.nix`
- [ ] 3.2 Guard the Home Assistant virtual host with `lib.mkIf config.scetrov.services.home-assistant.enable`
- [ ] 3.3 Set `useACMEHost = "scetrov.live";`
- [ ] 3.4 Configure Caddy to reverse proxy to `127.0.0.1:8123` with `header_up Host {upstream_hostport}`
- [ ] 3.5 Add an `@auth_routes` matcher that applies to `/` while excluding `/api/webhook/*` and `/api/websocket`
- [ ] 3.6 Apply the existing Authentik Caddy `forward_auth` outpost pattern to `@auth_routes`

## 4. Static Verification

- [ ] 4.1 Validate Nix formatting or syntax using the repository's established checks for changed Nix files
- [ ] 4.2 Confirm the generated Caddy configuration syntax is valid with the repository's deployment or validation workflow
- [ ] 4.3 Confirm no secrets, tokens, keys, connection strings, or generated state files were added
- [ ] 4.4 Stage all required files for commit after verification

## 5. Deploy-Time Verification

- [ ] 5.1 Deploy narrowly to `habiki` using a targeted command such as `./scripts/play.sh --limit habiki --tags nixos`
- [ ] 5.2 Verify the `homeassistant` OCI container reports active and healthy under Podman on `habiki`
- [ ] 5.3 Verify `ss -tulpn` shows Home Assistant listening on `127.0.0.1:8123`
- [ ] 5.4 Verify host firewall rules allow inbound UDP ports `1900` and `5353`
- [ ] 5.5 Verify `curl -I https://homeassistant.net.scetrov.live/` returns an Authentik challenge or redirect
- [ ] 5.6 Verify `curl -I https://homeassistant.net.scetrov.live/api/websocket` bypasses the Authentik challenge and reaches Home Assistant
- [ ] 5.7 Verify Loki can query Home Assistant logs by `{container_name="homeassistant"}` or `{unit="podman-homeassistant.service"}`
- [ ] 5.8 After Home Assistant internal integrations are configured, verify metrics in Mimir/Prometheus and traces through the Caddy `/otlp*` route into Tempo
