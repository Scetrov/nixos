## 1. Update Operations Platform Overview

- [x] 1.1 Replace the legacy 5-hour and 7-day Codex stat panels with `Weekly Remaining` and `Weekly Reset` panels in `terraform/dashboards/platform-overview.json`, retaining the existing overview layout and Mimir datasource.
- [x] 1.2 Implement the semantic weekly allowance and reset PromQL expressions with authentication, scrape-success, weekly-presence, and two-poll freshness gates so unavailable data renders as `N/A`.
- [x] 1.3 Configure the remaining-allowance thresholds and reset duration unit using the approved Heart Pumps Neon palette and existing dashboard conventions.

## 2. Validate and Deploy

- [x] 2.1 Extend dashboard tests to validate the Operations Platform Overview panel titles, PromQL gates, weekly labels, datasource, duration unit, palette thresholds, and absence of retired fixed-window labels.
- [x] 2.2 Run dashboard JSON parsing, relevant unit tests, OpenTofu formatting and validation through `scripts/tofu.sh`, and a sensitive-material scan.
- [x] 2.3 Apply the dashboard through `scripts/tofu.sh` and verify in Grafana that fresh data displays weekly remaining allowance and reset time while stale, failed, unauthenticated, or absent-weekly states display `N/A`.
