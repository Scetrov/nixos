# Home Assistant Optimization and Tasks

## ADDED Requirements

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
- **THEN** the module installs those files into `/var/lib/homeassistant` with deterministic permissions

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

- **GIVEN** a requested device, protocol, or service is supported by an official Home Assistant integration
- **WHEN** the implementation designs the integration
- **THEN** it uses the official integration unless a documented exception is approved

#### Scenario: Custom integration exception is required

- **GIVEN** a requested capability requires HACS or a custom integration
- **WHEN** the implementation proposes that dependency
- **THEN** the design documents the reason, versioning approach, rollback plan, and maintenance risk

### Requirement: Matter and Thread Readiness Review

The system SHALL evaluate Matter and Thread readiness without enabling protocol services until required hardware and integration choices are confirmed.

#### Scenario: Protocol readiness is assessed

- **GIVEN** Matter or Thread support is considered for Home Assistant
- **WHEN** the optimization audit runs
- **THEN** it records available host hardware, border router dependencies, official integration options, and follow-up implementation tasks

### Requirement: Home Assistant Dashboard Organization Review

The system SHALL review dashboard organization and determine whether dashboards should remain UI-managed or become repository-managed artifacts.

#### Scenario: Dashboard inventory is captured

- **GIVEN** Home Assistant dashboards exist in live storage
- **WHEN** the optimization audit inspects live state
- **THEN** it records dashboard names, source storage location, and whether each dashboard is a candidate for declarative management
