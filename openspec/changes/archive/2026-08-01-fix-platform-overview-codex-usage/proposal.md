## Why

The Operations Platform Overview still queries retired Codex `5h` and `7d` metric labels. The app-server migration deliberately emits only duration-derived windows and the current account exposes a weekly window, leaving both overview cards without current data. Operators therefore cannot see remaining Codex allowance or its reset time from the overview.

## What Changes

- Replace the obsolete "5-Hour Window" and "7-Day Window" overview cards with "Weekly Remaining" and "Weekly Reset" cards.
- Calculate remaining allowance from the semantic weekly usage metric and calculate reset time from the absolute weekly reset timestamp.
- Gate both current-value cards on explicit Codex authentication, successful collection, weekly-window presence, and the existing two-poll freshness threshold; show `N/A` when those conditions are not met.
- Extend dashboard validation to cover the Operations Platform Overview Codex queries and prohibit retired fixed-window labels.

## Capabilities

### New Capabilities

- `platform-overview-ai-usage`: Defines the freshness-safe Codex allowance and reset information shown on the Operations Platform Overview dashboard.

### Modified Capabilities

- None.

## Impact

- Updates `terraform/dashboards/platform-overview.json` and its dashboard tests.
- Uses existing `ai-usage-exporter` metrics already scraped by Alloy and written to Mimir; no exporter, Alloy, API, secret, port, or route change is expected.
- Dashboard provisioning continues through the existing OpenTofu configuration and `scripts/tofu.sh` wrapper.
