# Home Assistant Deployment Proposal

## Why

Home Assistant needs to run on the `habiki` node as an automated, persistent service while preserving LAN discovery behavior for smart-home integrations. It also needs to be reachable through the existing Caddy and Authentik edge pattern without exposing the UI directly or breaking webhook, WebSocket, mobile app, telemetry, and local discovery flows.

## What Changes

- Add a declarative NixOS module for a Podman-backed Home Assistant OCI container using `ghcr.io/home-assistant/home-assistant:stable`.
- Persist Home Assistant configuration under `/var/lib/homeassistant` and create the directory with systemd tmpfiles.
- Enable host networking for Home Assistant and open UDP discovery ports for SSDP and mDNS when the service is active.
- Enable the module on `habiki` using the repository's `scetrov.services.*` namespace.
- Add a Caddy virtual host for `homeassistant.net.scetrov.live` using the wildcard certificate and existing Authentik forward-auth pattern.
- Exempt Home Assistant webhook and WebSocket endpoints from Authentik interception while protecting the root UI route.
- Document the required manual Home Assistant `http.trusted_proxies` configuration for reverse-proxy correctness.

## Capabilities

### New Capabilities

- `home-assistant-platform`: Declarative Home Assistant deployment, LAN discovery networking, Caddy ingress, Authentik boundaries, and post-deployment validation requirements.

### Modified Capabilities

None.

## Impact

- Adds `src/roles/nixos/files/etc/nixos/modules/home-assistant.nix`.
- Updates `src/roles/nixos/files/device-configuration/habiki.nix`.
- Updates `src/roles/nixos/files/etc/nixos/modules/caddy.nix`.
- Adds a new Podman container on `habiki` with host networking and persistent state.
- Adds inbound UDP firewall allowance for ports `1900` and `5353` only when Home Assistant is enabled.
- Adds a new HTTPS route under the existing `scetrov.live` wildcard certificate and Authentik outpost.
