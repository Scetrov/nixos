## MODIFIED Requirements

### Requirement: Project Zomboid activity history is interval-based
The system SHALL visualize the seven supported resettable native Project Zomboid game event totals as discrete interval event counts across the active Grafana dashboard time range: zombies killed, zombies killed by fire, corpses burned, players killed by zombies, players killed by fire, players killed by players, and zombified players. The interval SHALL be selected from the dashboard range with a configured minimum that ordinarily produces readable 5–15 minute buckets, rather than overlapping rolling-hour values. The dashboard SHALL identify zombies killed by fire as a subset of total zombies killed and SHALL NOT present those two series as independent additive totals.

#### Scenario: Operator inspects recent activity
- **WHEN** an operator opens a short or normal dashboard time range containing native game event samples
- **THEN** the dashboard SHALL render all seven supported event series as bar values for discrete time intervals
- **AND** each bar SHALL represent the increase during its own interval rather than a rolling preceding-hour total
- **AND** the zombie-fire series SHALL be labelled as included in the total zombie-kill series

#### Scenario: Native game-day total resets during the selected range
- **WHEN** a resettable native `-today` event total resets within an event interval
- **THEN** the dashboard SHALL derive the interval count using reset-aware increase semantics
- **AND** SHALL NOT present the reset as a negative event count

#### Scenario: Event telemetry is absent
- **WHEN** no samples exist for a requested event series in the active dashboard range
- **THEN** the dashboard SHALL identify the series as unavailable
- **AND** SHALL NOT display a zero count inferred from absent telemetry

### Requirement: Project Zomboid roster reflects dashboard-timeframe observations
The system SHALL present a player roster containing every player identity observed by verified native player-coordinate telemetry during the active Grafana dashboard time range. For each rostered player, the dashboard SHALL show the native Player ID, latest observation time as last seen, and the latest available World X and World Y game-tile coordinates. The roster SHALL NOT include health, days alive, or individual zombies-killed columns unless verified native per-player telemetry exists for those fields.

#### Scenario: Player disconnects after being observed
- **WHEN** a player has native coordinate telemetry earlier in the active dashboard range but is no longer online at the range end
- **THEN** the roster SHALL retain that player
- **AND** SHALL show the timestamp of the player’s latest observation as last seen

#### Scenario: Native coordinates are available
- **WHEN** verified native `player_x` and `player_y` telemetry is present for a rostered player
- **THEN** the roster SHALL show that player's latest World X and World Y coordinates in game tiles
- **AND** SHALL show the corresponding native Player ID

#### Scenario: Per-player status telemetry is unavailable
- **WHEN** the native endpoint does not expose per-player health, days alive, or individual zombies killed
- **THEN** the roster SHALL omit those unsupported columns
- **AND** SHALL NOT substitute zero or infer values from aggregate game or log telemetry

#### Scenario: Game master interprets roster scope
- **WHEN** a game master opens the roster
- **THEN** its title or description SHALL state that it covers players observed in the active dashboard time range
- **AND** SHALL NOT describe itself as a complete saved-character roster
