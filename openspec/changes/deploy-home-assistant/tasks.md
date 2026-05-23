# Home Assistant Deployment Tasks

## 1. NixOS Service Module

- [x] 1.1 Create `src/roles/nixos/files/etc/nixos/modules/home-assistant.nix` with `options.scetrov.services.home-assistant.enable = lib.mkEnableOption "Home Assistant service";`
- [x] 1.2 Gate all Home Assistant declarations with `lib.mkIf config.scetrov.services.home-assistant.enable`
- [x] 1.3 Declare `virtualisation.oci-containers.containers.homeassistant` using `ghcr.io/home-assistant/home-assistant:stable`
- [x] 1.4 Configure `/var/lib/homeassistant:/config`, `TZ = "Europe/London"`, and `extraOptions = [ "--network=host" ]`
- [x] 1.5 Add a `systemd.tmpfiles.rules` entry for `/var/lib/homeassistant` with mode `0750` and ownership `root root`
- [x] 1.6 Allow inbound UDP firewall ports `1900` and `5353` only while the Home Assistant module is enabled
- [x] 1.7 Manage the required Home Assistant `http.use_x_forwarded_for` and `trusted_proxies` YAML declaratively

## 2. Habiki Assignment

- [x] 2.1 Add `./modules/home-assistant.nix` to the `imports` list in `src/roles/nixos/files/device-configuration/habiki.nix`
- [x] 2.2 Set `scetrov.services.home-assistant.enable = true;` in `habiki.nix`
- [x] 2.3 Add `"homeassistant.net.scetrov.live"` to Habiki's IP mapping block `10.229.10.2` in `src/roles/nixos/files/etc/nixos/modules/local-networking.nix`

## 3. Caddy and Authentik Ingress

- [x] 3.1 Add `virtualHosts."homeassistant.net.scetrov.live"` inside the `services.caddy` block in `src/roles/nixos/files/etc/nixos/modules/caddy.nix`
- [x] 3.2 Guard the Home Assistant virtual host with `lib.mkIf config.scetrov.services.home-assistant.enable`
- [x] 3.3 Set `useACMEHost = "scetrov.live";`
- [x] 3.4 Configure Caddy to reverse proxy to `127.0.0.1:8123` while preserving the original request host
- [x] 3.5 Add an `@auth_routes` matcher that applies to `/` while excluding `/api/webhook/*`, `/api/websocket`, and `/auth/oidc/*`
- [x] 3.6 Apply the existing Authentik Caddy `forward_auth` outpost pattern to `@auth_routes`
- [x] 3.7 In `terraform/authentik.tf`, define the `authentik_provider_proxy.homeassistant`, `authentik_application.homeassistant`, and `authentik_policy_binding.homeassistant_access` resources
- [x] 3.8 Append `authentik_provider_proxy.homeassistant.id` to the `protocol_providers` list within the `authentik_outpost.proxy` resource block in `terraform/authentik.tf`
- [x] 3.9 Copy `home-assistant.png` into Authentik branding assets and set the Home Assistant application `meta_icon` to `/static/dist/branding/home-assistant.png`
- [x] 3.10 Define `authentik_provider_oauth2.homeassistant_oidc`, `authentik_application.homeassistant_oidc`, and `authentik_policy_binding.homeassistant_oidc_access` for native Home Assistant OIDC
- [x] 3.11 Vendor `hass-oidc-auth` v1.1.0 and install it into `/var/lib/homeassistant/custom_components/auth_oidc`
- [x] 3.12 Configure Home Assistant `auth_oidc` with the Authentik discovery URL and group role mappings
- [x] 3.13 Add a `home-assistant-bootstrap-owner` oneshot service that creates the first Home Assistant owner account only when `Total users: 0`

## 4. Static Verification

- [x] 4.1 Validate Nix formatting or syntax using the repository's established checks for changed Nix files
- [x] 4.2 Confirm the generated Caddy configuration syntax is valid with the repository's deployment or validation workflow
- [x] 4.3 Confirm no secrets, tokens, keys, connection strings, or generated state files were added
- [x] 4.4 Stage all required files for commit after verification

## 5. Deploy-Time Verification

- [x] 5.1 Deploy narrowly to `habiki` using a targeted command such as `./scripts/play.sh --limit habiki --tags nixos`
- [x] 5.2 Verify the `homeassistant` OCI container reports active/running under Podman on `habiki`
- [x] 5.3 Verify `ss -tulpn` shows Home Assistant listening on TCP port `8123`
- [x] 5.4 Verify host firewall rules allow inbound UDP ports `1900` and `5353`
- [x] 5.5 Verify `curl -I https://homeassistant.net.scetrov.live/` returns an Authentik challenge or redirect
- [x] 5.6 Verify `curl -I https://homeassistant.net.scetrov.live/api/websocket` bypasses the Authentik challenge and reaches Home Assistant
- [x] 5.7 Verify Loki can query Home Assistant logs by `{container_name="homeassistant"}` or `{unit="podman-homeassistant.service"}`
- [ ] 5.8 After Home Assistant internal integrations are configured, verify metrics in Mimir/Prometheus and traces through the Caddy `/otlp*` route into Tempo
