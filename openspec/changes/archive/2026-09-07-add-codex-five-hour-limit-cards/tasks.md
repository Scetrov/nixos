## 1. Update dashboard presentations

- [x] 1.1 Reorganize the AI Usage dashboard’s current-value cards to show `5-Hour Remaining`, `5-Hour Reset`, `Weekly Remaining`, and `Weekly Reset`, while retaining its OpenRouter and health panels.
- [x] 1.2 Add per-window freshness-, authentication-, scrape-success-, and presence-gated Mimir PromQL expressions for the 5-hour remaining allowance and reset countdown in the AI Usage dashboard.
- [x] 1.3 Reorganize the Operations Platform Overview capacity row to show both five-hour and weekly Codex remaining/reset card pairs without displacing unrelated observability content.
- [x] 1.4 Add equivalent guarded five-hour allowance and reset queries to the Operations Platform Overview, retaining the approved capacity colors, duration unit, and `N/A` behavior.

## 2. Add regression coverage

- [x] 2.1 Update AI Usage dashboard tests to require the 5-hour card pair, their semantic `window="5h"` queries, units, approved thresholds, and independent absence handling.
- [x] 2.2 Update Platform Overview dashboard tests to require both semantic window pairs, per-window freshness gates, Mimir datasource, and continued absence of the retired `window="7d"` label.

## 3. Validate and deploy

- [x] 3.1 Validate dashboard JSON and run the relevant AI usage exporter and dashboard test suites.
- [x] 3.2 Run OpenSpec validation, OpenTofu formatting and validation through `scripts/tofu.sh`, and a sensitive-material scan of changed files.
- [x] 3.3 Apply the dashboard update through `scripts/tofu.sh` and verify fresh five-hour/weekly values and `N/A` behavior for unavailable Codex data in Grafana.
