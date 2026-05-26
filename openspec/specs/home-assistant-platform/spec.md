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

### Requirement: Declarative Matter Server Backend

The system SHALL provide a declarative Matter Server backend for the container-based Home Assistant deployment when `scetrov.services.home-assistant.matter.enable` is enabled.

#### Scenario: Matter server disabled

- **WHEN** `scetrov.services.home-assistant.matter.enable` is false or unset
- **THEN** the Home Assistant platform does not declare a Matter server runtime, Matter state directory, or localhost websocket listener on port `5580`

#### Scenario: Matter server enabled

- **WHEN** `scetrov.services.home-assistant.matter.enable` is true on Habiki
- **THEN** the Home Assistant platform deploys an official Matter Server runtime on the same host as Home Assistant and exposes a websocket endpoint at `ws://localhost:5580/ws`

#### Scenario: Matter state persists across restarts

- **WHEN** the Matter server restarts or Habiki reboots
- **THEN** Matter pairing and controller state persist in a dedicated host-managed state directory outside Git

#### Scenario: Home Assistant uses the default Matter endpoint

- **WHEN** Home Assistant on Habiki configures the Matter integration with `ws://localhost:5580/ws`
- **THEN** the websocket connection succeeds without requiring a second Home Assistant instance

### Requirement: Runtime Verification

The implementation SHALL include verification steps for Home Assistant health, Matter websocket availability, host listeners, firewall discovery ports, Caddy validation, Authentik boundaries, and telemetry visibility.

#### Scenario: Post-deployment checks run

- **WHEN** Home Assistant with Matter server is deployed to `habiki`
- **THEN** verification confirms the `homeassistant` runtime is active, the Matter server runtime is active when enabled, TCP port `8123` is listening, the Matter websocket listener on port `5580` is reachable from Habiki, UDP ports `1900` and `5353` are allowed, Caddy validates successfully, Home Assistant OIDC routes are reachable, and logs are visible through the existing Loki pipeline

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

### Requirement: Home Assistant Configuration Audit

The system SHALL audit both committed and live Home Assistant configuration before applying optimizations that affect automations, scripts, scenes, dashboards, helpers, or integrations.

#### Scenario: Repository configuration is inventoried

- **GIVEN** the Home Assistant platform is managed by this repository
- **WHEN** the optimization work begins
- **THEN** the implementation inventories `home-assistant.nix`, generated `configuration.yaml` content, repository-managed Home Assistant assets, and OpenSpec requirements before editing behavior

#### Scenario: Live runtime configuration is compared

- **GIVEN** Home Assistant runtime state exists under `/var/lib/homeassistant` on `habiki`
- **WHEN** live-only files such as `automations.yaml`, `scripts.yaml`, `scenes.yaml`, blueprints, or dashboards are present
- **THEN** the implementation compares them against repository-managed files and records import decisions before replacing them

### Requirement: Declarative Home Assistant YAML Assets

The system SHALL manage reviewed Home Assistant YAML assets through the existing NixOS module rather than relying on untracked runtime files.

#### Scenario: Managed YAML files are installed

- **GIVEN** reviewed `automations.yaml`, `scripts.yaml`, or `scenes.yaml` files exist in the repository
- **WHEN** `./scripts/play.sh --limit habiki --tags nixos` applies the Home Assistant module
- **THEN** the files are installed into `/var/lib/homeassistant` with deterministic permissions

#### Scenario: Unreviewed runtime files are preserved

- **GIVEN** a live Home Assistant runtime file has not been reviewed for source control
- **WHEN** the Home Assistant module is deployed
- **THEN** the implementation MUST NOT overwrite that runtime file without an explicit import task and review outcome

### Requirement: Automation and Script Behavioral Specifications

The system SHALL define explicit behavior for every new or modified Home Assistant automation or script before implementation.

#### Scenario: Automation behavior is specified

- **GIVEN** a new or changed automation is proposed
- **WHEN** its implementation task is created
- **THEN** the task references a GIVEN/WHEN/THEN behavior describing trigger conditions, required entity state, and expected actions

#### Scenario: Script behavior is specified

- **GIVEN** a new or changed script is proposed
- **WHEN** its implementation task is created
- **THEN** the task references a GIVEN/WHEN/THEN behavior describing inputs, preconditions, and expected service calls

### Requirement: Integration Selection Policy

The system SHALL prefer official Home Assistant integrations and built-in configuration mechanisms before adding HACS or new custom integrations.

#### Scenario: Official integration exists

- **GIVEN** a desired capability can be provided by an official Home Assistant integration or built-in YAML/helper configuration
- **WHEN** an implementation approach is selected
- **THEN** the official or built-in option is chosen unless a documented exception exists

#### Scenario: Custom integration exception is required

- **GIVEN** a new HACS or custom integration is proposed
- **WHEN** it is not the existing `hass-oidc-auth` exception
- **THEN** the implementation documents why official integrations are insufficient, how the integration is deployed, and how it will be updated or removed

### Requirement: Matter and Thread Readiness Review

The system SHALL assess whether Matter or Thread support is useful before introducing protocol-specific configuration, and SHALL document Thread border-router ownership whenever Matter support is enabled for devices that depend on Thread transport.

#### Scenario: Protocol readiness is assessed

- **GIVEN** Matter or Thread support is considered for Home Assistant
- **WHEN** the optimization audit runs
- **THEN** it records available host hardware, border router dependencies, official integration options, and follow-up implementation tasks

#### Scenario: Thread border router ownership is recorded

- **GIVEN** the Matter server is being enabled for Home Assistant
- **WHEN** a target Matter device requires Thread transport
- **THEN** the implementation documents which border router provides Thread connectivity and does not treat the Matter server itself as the Thread border router

### Requirement: Home Assistant Dashboard Organization Review

The system SHALL review dashboard organization and determine whether dashboards should remain UI-managed or become repository-managed artifacts.

#### Scenario: Dashboard inventory is captured

- **GIVEN** live Home Assistant dashboards exist in `.storage` or repository-managed dashboard files
- **WHEN** the optimization audit runs
- **THEN** it records dashboard ownership, purpose, major entity groups, and any proposed cleanup or declarative migration tasks before changing dashboards

### Requirement: Declarative Home Assistant Prometheus Export
The system SHALL manage Home Assistant's internal Prometheus integration declaratively in the generated `configuration.yaml` and SHALL limit initial export scope to approved environmental entities.

#### Scenario: Prometheus integration is enabled declaratively
- **WHEN** the Home Assistant module is enabled on `habiki`
- **THEN** the generated `/var/lib/homeassistant/configuration.yaml` includes a managed `prometheus` configuration for Home Assistant's internal metrics endpoint

#### Scenario: Export scope is curated
- **WHEN** the managed Prometheus integration is rendered
- **THEN** it includes the approved environmental entities needed for dashboards, including supported temperature, humidity, CO2, PM2.5, PM10, and air-quality sensors, and excludes unrelated diagnostic, firmware, and Bluetooth signal entities from the initial export set

### Requirement: Local Prometheus Scrape Authentication
The system SHALL scrape Home Assistant metrics locally from Prometheus using an age-backed Home Assistant access token rather than exposing an unauthenticated public metrics path.

#### Scenario: Prometheus scrapes Home Assistant locally
- **WHEN** observability configuration is applied on `habiki`
- **THEN** Prometheus declares a Home Assistant scrape job that targets the local Home Assistant listener, uses Home Assistant's Prometheus metrics path, and attaches stable labels for at least `service=home-assistant`

#### Scenario: Scrape authentication is secret-backed
- **WHEN** the Home Assistant scrape job is configured
- **THEN** the authorization credential is sourced from a repo-managed age secret file and is not hardcoded into the NixOS module, Home Assistant configuration, or dashboard definitions

### Requirement: Environmental Metrics Validation
The system SHALL verify that Home Assistant environmental metrics flow through the existing Prometheus and Mimir path after deployment.

#### Scenario: Metrics are queryable after rollout
- **WHEN** the Home Assistant Prometheus integration and scrape job are deployed
- **THEN** validation confirms that the Home Assistant target is up in Prometheus and that exported environmental metrics are queryable through both the local Prometheus instance and the Mimir-backed Grafana datasource path

### Requirement: Declarative Home Assistant Bluetooth Access

The system SHALL provide an opt-in Bluetooth access mode for the container-based Home Assistant deployment.

#### Scenario: Bluetooth access disabled

- **WHEN** `scetrov.services.home-assistant.bluetooth.enable` is false or unset
- **THEN** the module does not enable host Bluetooth support for Home Assistant, does not mount `/run/dbus` into the Home Assistant container, and does not add Bluetooth-specific container capabilities

#### Scenario: Bluetooth access enabled

- **WHEN** `scetrov.services.home-assistant.bluetooth.enable` is true
- **THEN** the module enables the host Bluetooth stack, makes the host system D-Bus socket available to the Home Assistant container as `/run/dbus:ro`, and adds the `NET_ADMIN` and `NET_RAW` capabilities to the Home Assistant container

### Requirement: Habiki Bluetooth Trial Assignment

The system SHALL enable Home Assistant Bluetooth access on the `habiki` node for a local SwitchBot BLE sensor trial.

#### Scenario: Habiki enables Bluetooth access

- **WHEN** `src/roles/nixos/files/device-configuration/habiki.nix` is evaluated
- **THEN** it sets `scetrov.services.home-assistant.bluetooth.enable = true`

### Requirement: Bluetooth Runtime Verification

The system SHALL verify the Bluetooth access path after deploying Home Assistant Bluetooth support.

#### Scenario: Host Bluetooth is available

- **WHEN** Home Assistant Bluetooth access is deployed to `habiki`
- **THEN** verification confirms the host Bluetooth service is active and a Bluetooth controller is visible to BlueZ

#### Scenario: Container can access BlueZ over D-Bus

- **WHEN** Home Assistant Bluetooth access is deployed to `habiki`
- **THEN** verification confirms the Home Assistant container has access to `/run/dbus` and Home Assistant logs do not report a missing BlueZ D-Bus service for the Bluetooth integration

#### Scenario: SwitchBot discovery is trialed

- **WHEN** Home Assistant Bluetooth access is deployed to `habiki`
- **THEN** the operator can add the official Home Assistant SwitchBot Bluetooth integration and assess whether local Habiki Bluetooth coverage is sufficient for nearby SwitchBot temperature and humidity sensors
