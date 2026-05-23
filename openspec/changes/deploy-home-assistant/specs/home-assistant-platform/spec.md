# Home Assistant Platform Specification

## ADDED Requirements

### Requirement: Declarative Home Assistant Service Module

The system SHALL provide a NixOS module at `src/roles/nixos/files/etc/nixos/modules/home-assistant.nix` with the option `scetrov.services.home-assistant.enable`, and all Home Assistant service configuration MUST be gated by that option.

#### Scenario: Service disabled

- **WHEN** `scetrov.services.home-assistant.enable` is false or unset
- **THEN** the Home Assistant container, state directory tmpfiles rule, and firewall discovery ports are not declared by the module

#### Scenario: Service enabled

- **WHEN** `scetrov.services.home-assistant.enable` is true
- **THEN** the module declares `virtualisation.oci-containers.containers.homeassistant` using `ghcr.io/home-assistant/home-assistant:stable`, `TZ = "Europe/London"`, `/var/lib/homeassistant:/config`, and `--network=host`

### Requirement: Persistent State Directory

The system SHALL create `/var/lib/homeassistant` declaratively before the container requires it.

#### Scenario: NixOS activation prepares storage

- **WHEN** the Home Assistant module is enabled and NixOS activation applies tmpfiles
- **THEN** `/var/lib/homeassistant` exists with mode `0755` and ownership `root root`

### Requirement: LAN Discovery Firewall

The system SHALL allow inbound UDP discovery traffic required by Home Assistant local integrations only when Home Assistant is enabled.

#### Scenario: Discovery ports are opened

- **WHEN** the Home Assistant module is enabled
- **THEN** the host firewall allows inbound UDP ports `1900` and `5353`

### Requirement: Habiki Node Assignment

The system SHALL assign Home Assistant to the `habiki` node by importing the module and enabling the custom service option.

#### Scenario: Habiki configuration includes Home Assistant

- **WHEN** `src/roles/nixos/files/device-configuration/habiki.nix` is evaluated
- **THEN** it imports `./modules/home-assistant.nix` and sets `scetrov.services.home-assistant.enable = true`

### Requirement: Caddy Ingress

The system SHALL expose Home Assistant at `homeassistant.net.scetrov.live` through Caddy only when the Home Assistant service is enabled.

#### Scenario: Virtual host is enabled

- **WHEN** `scetrov.services.home-assistant.enable` is true
- **THEN** Caddy declares `virtualHosts."homeassistant.net.scetrov.live"` with `useACMEHost = "scetrov.live"` and proxies to `127.0.0.1:8123`

#### Scenario: Virtual host is disabled

- **WHEN** `scetrov.services.home-assistant.enable` is false or unset
- **THEN** Caddy does not declare the `homeassistant.net.scetrov.live` virtual host

### Requirement: Authentik Route Boundaries

The system SHALL protect the Home Assistant root UI route through the existing Authentik Caddy forward-auth outpost while excluding webhook and WebSocket endpoints.

#### Scenario: UI route requires Authentik

- **WHEN** an unauthenticated client requests `https://homeassistant.net.scetrov.live/`
- **THEN** Caddy applies forward-auth to `http://127.0.0.1:9000/outpost.goauthentik.io/auth/caddy`

#### Scenario: Webhook route bypasses Authentik

- **WHEN** a client requests `https://homeassistant.net.scetrov.live/api/webhook/<token>`
- **THEN** the request bypasses Authentik forward-auth and is proxied directly to Home Assistant

#### Scenario: WebSocket route bypasses Authentik

- **WHEN** a client requests `https://homeassistant.net.scetrov.live/api/websocket`
- **THEN** the request bypasses Authentik forward-auth and is proxied directly to Home Assistant

### Requirement: Reverse Proxy Header Policy

The system SHALL forward Home Assistant traffic with a host header policy compatible with the upstream service.

#### Scenario: Caddy proxies to Home Assistant

- **WHEN** Caddy proxies a request to Home Assistant
- **THEN** the reverse proxy uses `header_up Host {upstream_hostport}`

### Requirement: Post-Deployment Home Assistant Proxy Configuration Reminder

The repository SHALL document that Home Assistant must trust the local Caddy proxy and internal proxy network in `/var/lib/homeassistant/configuration.yaml`.

#### Scenario: Operator reviews deployment notes

- **WHEN** the change is implemented
- **THEN** the repository includes a reminder to configure `http.use_x_forwarded_for = true` and trusted proxies `127.0.0.1` and `10.229.0.0/16`

### Requirement: Runtime Verification

The implementation SHALL include verification steps for container health, host listener, firewall discovery ports, Caddy validation, Authentik boundaries, and telemetry visibility.

#### Scenario: Post-deployment checks run

- **WHEN** Home Assistant is deployed to `habiki`
- **THEN** verification confirms the `homeassistant` container is active and healthy, `127.0.0.1:8123` is listening, UDP ports `1900` and `5353` are allowed, Caddy validates successfully, UI requests are challenged by Authentik, exempt API paths bypass Authentik, and logs are visible through the existing Loki pipeline

#### Scenario: Metrics and traces are enabled internally

- **WHEN** Home Assistant's internal Prometheus and OpenTelemetry integrations are configured
- **THEN** metrics are queryable through the existing Mimir/Prometheus path and traces sent through the Caddy `/otlp*` endpoint register in Tempo
