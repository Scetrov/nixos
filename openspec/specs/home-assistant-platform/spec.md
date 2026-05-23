# home-assistant-platform Specification

## Purpose
TBD - created by archiving change deploy-home-assistant. Update Purpose after archive.
## Requirements
### Requirement: Declarative Home Assistant Service Module

The system SHALL provide a NixOS module at `src/roles/nixos/files/etc/nixos/modules/home-assistant.nix` with the option `scetrov.services.home-assistant.enable`, and all Home Assistant service configuration MUST be gated by that option.

#### Scenario: Service disabled

- **WHEN** `scetrov.services.home-assistant.enable` is false or unset
- **THEN** the Home Assistant container, state directory tmpfiles rule, and firewall discovery ports are not declared by the module

#### Scenario: Service enabled

- **WHEN** `scetrov.services.home-assistant.enable` is true
- **THEN** the module declares `virtualisation.oci-containers.containers.homeassistant` using `ghcr.io/home-assistant/home-assistant:stable`, `TZ = "Europe/London"`, `/var/lib/homeassistant:/config`, and `--network=host`

#### Scenario: Core locale settings are preconfigured

- **WHEN** Home Assistant starts from the declarative configuration
- **THEN** core settings use `Europe/London`, elevation `50`, currency `GBP`, country `GB`, and language `en-GB`

### Requirement: Persistent State Directory

The system SHALL create `/var/lib/homeassistant` declaratively before the container requires it.

#### Scenario: NixOS activation prepares storage

- **WHEN** the Home Assistant module is enabled and NixOS activation applies tmpfiles
- **THEN** `/var/lib/homeassistant` exists with mode `0750` and ownership `root root`

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

### Requirement: Native OIDC Route Boundaries

The system SHALL expose Home Assistant through Caddy without Authentik forward-auth because Home Assistant performs native Authentik OIDC authentication.

#### Scenario: UI route reaches Home Assistant

- **WHEN** a client requests `https://homeassistant.net.scetrov.live/`
- **THEN** Caddy proxies the request directly to Home Assistant

#### Scenario: Webhook route reaches Home Assistant

- **WHEN** a client requests `https://homeassistant.net.scetrov.live/api/webhook/<token>`
- **THEN** the request is proxied directly to Home Assistant

#### Scenario: WebSocket route reaches Home Assistant

- **WHEN** a client requests `https://homeassistant.net.scetrov.live/api/websocket`
- **THEN** the request is proxied directly to Home Assistant

#### Scenario: OIDC route reaches Home Assistant

- **WHEN** a client requests `https://homeassistant.net.scetrov.live/auth/oidc/callback`
- **THEN** the request is proxied directly to Home Assistant

### Requirement: Reverse Proxy Header Policy

The system SHALL forward Home Assistant traffic with a host header policy compatible with the upstream service.

#### Scenario: Caddy proxies to Home Assistant

- **WHEN** Caddy proxies a request to Home Assistant
- **THEN** the reverse proxy preserves the original request host

### Requirement: Managed Home Assistant Proxy Configuration

The system SHALL manage Home Assistant's reverse-proxy trust configuration in `/var/lib/homeassistant/configuration.yaml`.

#### Scenario: Configuration includes trusted proxies

- **WHEN** the Home Assistant module is enabled
- **THEN** `/var/lib/homeassistant/configuration.yaml` includes `http.use_x_forwarded_for = true` and trusted proxies `127.0.0.1`, `::1`, and `10.229.0.0/16`

### Requirement: Native Home Assistant OIDC

The system SHALL install `hass-oidc-auth` and configure Home Assistant to authenticate through Authentik using OpenID Connect.

#### Scenario: Home Assistant OIDC configuration is managed

- **WHEN** the Home Assistant module is enabled
- **THEN** `/var/lib/homeassistant/custom_components/auth_oidc` contains the vendored `hass-oidc-auth` integration and `configuration.yaml` contains `auth_oidc.client_id = "home-assistant"` with discovery URL `https://identity.net.scetrov.live/application/o/home-assistant-oidc/.well-known/openid-configuration`

### Requirement: Home Assistant Owner Bootstrap

The system SHALL create an initial Home Assistant owner account declaratively when no non-system users exist, so native authentication can proceed without manual onboarding.

#### Scenario: No users exist after first deployment

- **WHEN** the Home Assistant container is running and `python -m homeassistant --script auth -c /config list` reports `Total users: 0`
- **THEN** a systemd oneshot service generates `/var/lib/homeassistant/.bootstrap-owner-password` with mode `0600` if missing and creates the `scetrov-bootstrap` Home Assistant user

### Requirement: Runtime Verification

The implementation SHALL include verification steps for container health, host listener, firewall discovery ports, Caddy validation, Authentik boundaries, and telemetry visibility.

#### Scenario: Post-deployment checks run

- **WHEN** Home Assistant is deployed to `habiki`
- **THEN** verification confirms the `homeassistant` container is active/running, TCP port `8123` is listening, UDP ports `1900` and `5353` are allowed, Caddy validates successfully, Home Assistant OIDC routes are reachable, and logs are visible through the existing Loki pipeline

#### Scenario: Metrics and traces are enabled internally

- **WHEN** Home Assistant's internal Prometheus and OpenTelemetry integrations are configured
- **THEN** metrics are queryable through the existing Mimir/Prometheus path and traces sent through the Caddy `/otlp*` endpoint register in Tempo

### Requirement: Local DNS Resolution

The system SHALL ensure that `homeassistant.net.scetrov.live` is resolvable on the local network to the Habiki host.

#### Scenario: Host resolution resolves locally

- WHEN `local-networking.nix` is loaded
- THEN `"homeassistant.net.scetrov.live"` is listed under Habiki's IP address (`10.229.10.2`)

### Requirement: Authentik Ingress Declarative Provisioning

The system SHALL register the Home Assistant proxy application in Authentik via OpenTofu.

#### Scenario: Apply OpenTofu configurations

- WHEN `terraform/authentik.tf` is applied
- THEN it creates an `authentik_provider_proxy` with external host `https://homeassistant.net.scetrov.live`, associates it with a new `authentik_application`, registers the provider in `authentik_outpost.proxy.protocol_providers`, and binds access to the `all_applications` group.

### Requirement: Authentik OIDC Provider Declarative Provisioning

The system SHALL register a public Authentik OAuth2/OpenID provider for Home Assistant native OIDC login via OpenTofu.

#### Scenario: Apply OpenTofu OIDC configurations

- WHEN `terraform/authentik.tf` is applied
- THEN it creates an `authentik_provider_oauth2` with client ID `home-assistant`, strict redirect URI `https://homeassistant.net.scetrov.live/auth/oidc/callback`, and an application slug `home-assistant-oidc`.
