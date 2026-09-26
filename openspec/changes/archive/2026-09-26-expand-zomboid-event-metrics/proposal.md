## Why

The Project Zomboid Build 42 native `/metrics` endpoint exposes four verified daily event totals that the Events per interval chart currently omits. Adding them gives operators and game masters a fuller view of lethal player outcomes, fire-related activity, and zombification without inventing signals or relying on logs.

## What Changes

- Expand the Project Zomboid Events per interval chart with reset-aware interval increases for the verified native `connection` series: `zombies-killed-by-fire-today`, `players-killed-by-fire-today`, `players-killed-by-player-today`, and `zombified-players-today`.
- Preserve the existing interval bucketing, minimum interval, and unavailable-not-zero behavior for every event series.
- Label fire-killed zombies as a subset of total zombie kills, rather than implying it is an independent total suitable for stacking.
- Update the native telemetry contract and dashboard guidance to document the complete verified set of daily event totals and their semantics.
- Refine the player roster to show verified Player ID, last-seen, World X, and World Y fields, rather than placeholder columns for health, days alive, and individual zombies killed that the native endpoint does not expose.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `project-zomboid-dashboard-activity-history`: Expand the supported native event series rendered as discrete dashboard intervals while preserving truthful reset and absent-telemetry handling.

## Impact

- `terraform/dashboards/project-zomboid-service.json` — Events per interval and player-roster panel queries, transformations, labels, colours, and explanatory text.
- `docs/project-zomboid-observability.md` — verified native daily-event metric inventory and interpretation guidance.
- Project Zomboid Build 42’s private `http://127.0.0.1:9105/metrics` endpoint remains the source; no exporter, endpoint exposure, RCON, alert, or dependency change is required.
