## MODIFIED Requirements

### Requirement: Project Zomboid dashboard combines operator and game-master views
The system SHALL provide a declaratively managed Project Zomboid service dashboard with playability, world activity, game runtime, GM detail, and operational-evidence sections.

#### Scenario: Operator opens the service dashboard
- **WHEN** an operator opens the Project Zomboid dashboard
- **THEN** the landing view shows server availability and telemetry freshness alongside supported player, game-runtime, and world-health signals

#### Scenario: Game-master inspects player detail
- **WHEN** native telemetry exposes player data and a game master selects a player using the compact selector
- **THEN** the dashboard shows a roster of players observed in the active dashboard time range, including last-seen time and latest supported status values
- **AND** the dashboard shows a half-width, approximately game-map-proportioned player-path panel using the installed Build 42 basemap and aligned world X/Y coordinates rather than an Earth map

#### Scenario: No player coordinate is available
- **WHEN** no player coordinate is emitted for the selected time range
- **THEN** the roster SHALL indicate unavailable rather than zero, and the map SHALL show no position
- **AND** no redundant location-coverage or map-empty-state panel SHALL occupy dashboard space

#### Scenario: Operator reads the compact overview
- **WHEN** the operator opens the dashboard
- **THEN** stat panels SHALL show a title and prominent value rather than long query labels
- **AND** extended signal documentation SHALL start collapsed under More info
- **AND** different plotted signals SHALL have readable, visually distinct keys

#### Scenario: Interval game events are plotted
- **WHEN** native game-day event totals are available
- **THEN** the event chart SHALL show discrete interval increases derived from those resettable totals, labelled as events per interval rather than raw `-today` series or rolling-hour values
