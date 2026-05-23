# Home Assistant Deployment Design Document

## Context

The repository manages `habiki` host services declaratively through NixOS modules and uses `virtualisation.oci-containers` with Podman for container workloads. Public and internal HTTPS ingress is handled by the existing Caddy module, with Authentik forward-auth protecting selected application routes.

Home Assistant has requirements that differ from typical HTTP-only applications. Smart-home integrations rely on LAN discovery traffic such as SSDP and mDNS, so the container needs host networking rather than a default isolated Podman bridge. Home Assistant also requires explicit trusted proxy configuration in its own `configuration.yaml` before it will safely honor reverse-proxy headers.

## Goals / Non-Goals

**Goals:**

- Deploy Home Assistant on `habiki` through a dedicated `scetrov.services.home-assistant.enable` NixOS module option.
- Persist Home Assistant state under `/var/lib/homeassistant`.
- Preserve local discovery behavior through host networking and explicit firewall openings for UDP ports `1900` and `5353`.
- Expose `homeassistant.net.scetrov.live` through the existing Caddy wildcard certificate and Authentik forward-auth pattern.
- Protect the root UI route while exempting webhook and WebSocket endpoints required by external automations and companion clients.
- Declaratively provision the Authentik proxy provider, application, policy binding, and outpost binding in OpenTofu.
- Register the Home Assistant DNS alias in local-networking.nix to ensure split-horizon LAN resolution.
- Document post-deployment Home Assistant YAML that cannot be safely inferred by Caddy alone.

**Non-Goals:**

- Automating Home Assistant's internal onboarding, integrations, `configuration.yaml`, Prometheus component, or OpenTelemetry component.
- Changing the existing Caddy, Authentik, Alloy, Mimir, Tempo, or Loki architectures beyond adding the Home Assistant route.

## Decisions

- Use a dedicated NixOS module named `home-assistant.nix`.
  - Rationale: This matches the repository pattern of service-specific modules gated by custom `scetrov.services.*` options.
  - Alternative considered: Inline all configuration in `habiki.nix`; rejected because it would mix service implementation with node assignment.

- Use `virtualisation.oci-containers.containers.homeassistant` with `ghcr.io/home-assistant/home-assistant:stable`.
  - Rationale: This follows the requested containerized Podman path and keeps updates aligned with Home Assistant's published stable image.
  - Alternative considered: Native NixOS `services.home-assistant`; rejected because the request explicitly requires containerized Podman.

- Use `--network=host`.
  - Rationale: Host networking is the least fragile way to preserve multicast and local broadcast discovery needed by integrations such as Hue, Sonoff LAN, and voice-assistant broadcast targets.
  - Alternative considered: Bridge networking plus explicit port mappings; rejected because multicast discovery is unreliable and incomplete in that topology.

- Add Caddy route-level Authentik enforcement rather than relying on Home Assistant authentication alone.
  - Rationale: The infrastructure standard requires IdAM handling through Authentik for exposed applications.
  - Alternative considered: Leave Home Assistant directly exposed behind TLS; rejected because it bypasses the established IdAM boundary for browser UI access.

- Exempt `/api/webhook/*` and `/api/websocket` from Authentik forward-auth.
  - Rationale: Webhooks and companion clients need to reach Home Assistant directly using Home Assistant's own authentication or webhook tokens.
  - Alternative considered: Apply Authentik to all paths; rejected because it would break external webhook delivery and WebSocket clients that cannot complete browser-centric Authentik flows.

## Risks / Trade-offs

- [Risk] Host networking increases container access to the host network namespace. Mitigation: keep the service scoped to `habiki`, avoid extra published ports, and rely on firewall and Caddy boundaries for external access.
- [Risk] Authentik protection of only the root UI path may not cover every browser route if Home Assistant serves additional UI paths outside `/`. Mitigation: validate route behavior after deployment and adjust the Caddy matcher if Home Assistant UI routes require broader protection.
- [Risk] Home Assistant may reject forwarded headers until `configuration.yaml` is updated. Mitigation: add a repository reminder and include post-deployment verification for the required `http.use_x_forwarded_for` and `trusted_proxies` settings.
- [Risk] Telemetry availability depends on Home Assistant internal integrations. Mitigation: require logs through the existing container journald/Loki path and document that Prometheus and OpenTelemetry become active once configured inside Home Assistant.

## Migration Plan

1. Add the Home Assistant NixOS module, node import, service enablement, and Caddy virtual host.
2. Deploy with a targeted run such as `./scripts/play.sh --limit habiki --tags nixos`.
3. Add the Home Assistant `http.trusted_proxies` settings to `/var/lib/homeassistant/configuration.yaml`.
4. Restart Home Assistant if the internal YAML changed.
5. Verify the container, listener, firewall, Caddy syntax, Authentik route behavior, bypassed API paths, and observability queries.

Rollback is to disable `scetrov.services.home-assistant.enable`, remove or leave the persistent `/var/lib/homeassistant` data directory according to recovery needs, and redeploy `habiki`.
