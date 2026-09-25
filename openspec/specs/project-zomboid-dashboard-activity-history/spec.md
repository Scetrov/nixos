# project-zomboid-dashboard-activity-history Specification

## Purpose
TBD - created by archiving change improve-game-dashboard. Update Purpose after archive.
## Requirements
### Requirement: Project Zomboid activity history is interval-based
The system SHALL visualize supported resettable native game event totals as discrete interval event counts across the active Grafana dashboard time range. The interval SHALL be selected from the dashboard range with a configured minimum that ordinarily produces readable 5–15 minute buckets, rather than overlapping rolling-hour values.

#### Scenario: Operator inspects recent activity
- **WHEN** an operator opens a short or normal dashboard time range containing native game event samples
- **THEN** the dashboard SHALL render zombies killed, corpses burned, and player deaths as bar values for discrete time intervals
- **AND** each bar SHALL represent the increase during its own interval rather than a rolling preceding-hour total

#### Scenario: Native game-day total resets during the selected range
- **WHEN** a resettable native `-today` event total resets within an event interval
- **THEN** the dashboard SHALL derive the interval count using reset-aware increase semantics
- **AND** SHALL NOT present the reset as a negative event count

#### Scenario: Event telemetry is absent
- **WHEN** no samples exist for a requested event series in the active dashboard range
- **THEN** the dashboard SHALL identify the series as unavailable
- **AND** SHALL NOT display a zero count inferred from absent telemetry

### Requirement: Project Zomboid roster reflects dashboard-timeframe observations
The system SHALL present a player roster containing every player identity observed by verified native player telemetry during the active Grafana dashboard time range. For each rostered player, the dashboard SHALL show the latest observation time as last seen and SHALL show the latest available health, days alive, and zombies killed values when those native metrics are supported.

#### Scenario: Player disconnects after being observed
- **WHEN** a player has native telemetry earlier in the active dashboard range but is no longer online at the range end
- **THEN** the roster SHALL retain that player
- **AND** SHALL show the timestamp of the player’s latest observation as last seen

#### Scenario: Native player status fields are available
- **WHEN** verified native telemetry exposes health, days alive, or zombies killed for a rostered player during the active dashboard range
- **THEN** the roster SHALL display the latest observed value for each available field

#### Scenario: Native player status field is unavailable
- **WHEN** a requested player status metric is not exposed or has no observation for a rostered player in the active dashboard range
- **THEN** the roster SHALL identify that field as unavailable
- **AND** SHALL NOT substitute zero or an inferred value

#### Scenario: Game master interprets roster scope
- **WHEN** a game master opens the roster
- **THEN** its title or description SHALL state that it covers players observed in the active dashboard time range
- **AND** SHALL NOT describe itself as a complete saved-character roster
