## Why

The Project Zomboid dashboard’s rolling-hour event graph fails to communicate discrete activity over time, and its online-only roster loses players as soon as they disconnect. Game masters need interval-based event counts and a dashboard-window roster that preserves each observed player’s latest known state.

## What Changes

- Replace the rolling-hour event time series with a bar chart of event totals per Grafana-selected interval (targeting a readable 5–15 minute bucket width).
- Derive each bucket from resettable native game-day totals without treating missing telemetry as zero.
- Replace the online-only player roster with a dashboard-timeframe roster that includes players observed during the selected range and their last-seen time.
- Include the latest available health, days alive, and zombies killed values for each rostered player when native telemetry provides them, and mark unavailable values truthfully.
- Rename and describe the GM roster section to reflect its historical dashboard-window scope while retaining player-path selection behavior.

## Capabilities

### New Capabilities

- `project-zomboid-dashboard-activity-history`: Interval event visualization and dashboard-timeframe player roster behavior for Project Zomboid operators and game masters.

### Modified Capabilities

- `project-zomboid-observability`: Changes the Project Zomboid dashboard’s event and player-detail requirements.

## Impact

- Updates `terraform/dashboards/project-zomboid-service.json` and its declarative Grafana provisioning path.
- Depends on verified Project Zomboid native Prometheus metric names and labels for player status fields.
- Requires dashboard validation against the managed Prometheus datasource and the dashboard time-range controls; no new network exposure, credentials, alerts, or runtime services are introduced.
