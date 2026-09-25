## ADDED Requirements

### Requirement: Project Zomboid native metrics remain private
The system SHALL enable and ingest Project Zomboid Build 42 native Prometheus telemetry without enabling RCON, requiring client software, or exposing the telemetry listener on LAN, Headscale, or WAN interfaces.

#### Scenario: Native endpoint is privately scraped
- **WHEN** the Project Zomboid service is running with native telemetry enabled
- **THEN** the existing managed Prometheus-compatible telemetry path scrapes the endpoint through a private local path and retains the resulting metrics in the managed metrics datasource

#### Scenario: No remote administration is added
- **WHEN** the Project Zomboid observability configuration is inspected or deployed
- **THEN** RCON remains disabled and no RCON credential, public listener, or client-side telemetry dependency is introduced

### Requirement: Native game telemetry coverage is verified and semantically accurate
The system SHALL verify native metric names, labels, listener behavior, and supported signal coverage on the deployed Build 42 server before dashboard queries are finalized. Dashboard labels SHALL preserve the native semantic distinction between global, simulated, and loaded world counters.

#### Scenario: Supported signals are shown truthfully
- **WHEN** the deployed native endpoint exposes an unambiguous player, world, runtime, or network signal
- **THEN** the dashboard queries the verified metric and presents the value using its native semantics

#### Scenario: Requested native signal is unavailable
- **WHEN** the deployed native endpoint does not expose a requested signal such as animal instances or server tick rate
- **THEN** the dashboard identifies that signal as unavailable and SHALL NOT display it as zero or infer it from a different metric

### Requirement: Project Zomboid dashboard combines operator and game-master views
The system SHALL provide a declaratively managed Project Zomboid service dashboard with playability, world activity, game runtime, GM detail, and operational-evidence sections.

#### Scenario: Operator opens the service dashboard
- **WHEN** an operator opens the Project Zomboid dashboard
- **THEN** the landing view shows server availability and telemetry freshness alongside supported player, game-runtime, and world-health signals

#### Scenario: Game-master inspects player detail
- **WHEN** native telemetry exposes player coordinate data and a game master selects a player using the compact selector
- **THEN** the dashboard shows an online-player roster and a half-width, approximately game-map-proportioned player-path panel using the installed Build 42 basemap and aligned world X/Y coordinates rather than an Earth map

#### Scenario: No player coordinate is available
- **WHEN** no online player coordinate is emitted for the selected time range
- **THEN** the roster SHALL indicate unavailable rather than zero, and the map SHALL show no position
- **AND** no redundant location-coverage or map-empty-state panel SHALL occupy dashboard space

#### Scenario: Operator reads the compact overview
- **WHEN** the operator opens the dashboard
- **THEN** stat panels SHALL show a title and prominent value rather than long query labels
- **AND** extended signal documentation SHALL start collapsed under More info
- **AND** different plotted signals SHALL have readable, visually distinct keys

#### Scenario: Hourly game events are plotted
- **WHEN** native game-day event totals are available
- **THEN** the event chart SHALL show approximate rolling-hour increases derived from those resettable totals, labelled as hourly events rather than raw `-today` series

### Requirement: Game resource telemetry is attributed to the service
The Project Zomboid dashboard SHALL show only game/JVM or `project-zomboid.service`-attributable CPU and memory telemetry, not host-wide CPU or memory measurements presented as game consumption.

#### Scenario: Attributable resource telemetry exists
- **WHEN** a verified JVM or service-cgroup CPU or memory signal is available
- **THEN** the dashboard displays it as Project Zomboid runtime resource consumption

#### Scenario: Attributable resource telemetry is not available
- **WHEN** no trustworthy Project Zomboid CPU or memory signal is available
- **THEN** the dashboard identifies that runtime signal as unavailable and links operators to the existing host resource dashboard rather than substituting a host-wide measurement

### Requirement: Project Zomboid logs are correlated with game telemetry
The system SHALL label Project Zomboid journal logs with stable `service="project-zomboid"` and `host` identities and expose both focused and chronological log views on the service dashboard.

#### Scenario: Operator reviews actionable logs
- **WHEN** an operator opens the Project Zomboid dashboard
- **THEN** it provides a focused warning/error log view and a full recent chronological log view filtered by the Project Zomboid service identity

#### Scenario: Cross-signal correlation is available
- **WHEN** Project Zomboid metrics and logs are queried in Grafana
- **THEN** both signals can be correlated using the stable service identity and host identity

### Requirement: Project Zomboid observability does not add alert rules
The system SHALL not create Project Zomboid alert rules, notification policies, or paging routes as part of this change.

#### Scenario: Dashboard is provisioned
- **WHEN** the Project Zomboid dashboard and telemetry configuration are applied
- **THEN** visual health signals are available in Grafana without introducing automated alert evaluation or notification behavior
