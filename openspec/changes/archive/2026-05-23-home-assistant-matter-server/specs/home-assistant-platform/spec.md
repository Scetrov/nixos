## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Runtime Verification
The implementation SHALL include verification steps for Home Assistant health, Matter websocket availability, host listeners, firewall discovery ports, Caddy validation, Authentik boundaries, and telemetry visibility.

#### Scenario: Post-deployment checks run
- **WHEN** Home Assistant with Matter server is deployed to `habiki`
- **THEN** verification confirms the `homeassistant` runtime is active, the Matter server runtime is active when enabled, TCP port `8123` is listening, the Matter websocket listener on port `5580` is reachable from Habiki, UDP ports `1900` and `5353` are allowed, Caddy validates successfully, Home Assistant OIDC routes are reachable, and logs are visible through the existing Loki pipeline

#### Scenario: Metrics and traces are enabled internally
- **WHEN** Home Assistant's internal Prometheus and OpenTelemetry integrations are configured
- **THEN** metrics are queryable through the existing Mimir/Prometheus path and traces sent through the Caddy `/otlp*` endpoint register in Tempo

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
