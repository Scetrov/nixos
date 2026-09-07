## Why

OpenAI/Codex now returns both a five-hour and a weekly subscription window. The dashboards show only the weekly allowance and reset, so operators cannot see the short-horizon capacity that determines whether work can continue immediately.

## What Changes

- Add freshness-safe `5h` remaining-allowance and reset cards to the detailed AI Usage dashboard alongside the existing weekly cards.
- Rework the Operations Platform Overview capacity row so it presents remaining allowance and reset countdowns for both provider-reported `5h` and `weekly` Codex windows.
- Treat the semantic `5h` label as valid only when the app-server actually returns the 300-minute window; absent, unauthenticated, failed, or stale data renders `N/A`.
- Update dashboard regression coverage and specifications to replace the prohibition on fixed `5h` labels while continuing to prohibit the retired `7d` label.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `ai-usage-dashboard`: Require current-value cards for both actual 5-hour and weekly Codex subscription windows.
- `platform-overview-ai-usage`: Require the platform overview to expose both actual 5-hour and weekly Codex subscription windows instead of only weekly values.

## Impact

- Updates `terraform/dashboards/ai-usage.json` and `terraform/dashboards/platform-overview.json` plus `src/roles/nixos/tests/test_ai_usage_dashboard.py`.
- Reuses existing exporter metrics—`ai_codex_window_used_percent`, `ai_codex_window_reset_timestamp_seconds`, and `ai_codex_window_present`—and does not alter the exporter, Codex app-server, Alloy, Mimir, credentials, ports, or routes.
- Dashboard provisioning remains declarative through the existing OpenTofu configuration and `scripts/tofu.sh` wrapper.
