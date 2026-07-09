## Why

Agentic coding is core to the development loop — ChatGPT 5.5 (Codex) via Pi for planning, and OpenRouter via Hermes WebUI for implementation. Today, tracking usage against limits requires manually checking two separate dashboards (ChatGPT's usage page and OpenRouter's credits page). There is no single pane of glass, no history, and no integration with the existing Grafana operations overview. This change brings AI usage visibility into the observability stack so remaining budget and burn rate are visible alongside infrastructure health in a single home page.

## What Changes

- **New Python exporter** (`ai-usage-exporter.py`) that polls the Codex `wham/usage` internal endpoint and OpenRouter `/credits` API, exposing Prometheus metrics for usage windows, credit balances, and rate-limit status
- **New NixOS module** (`ai-usage.nix`) defining the systemd service for the exporter, including secret mounting for Codex OAuth credentials
- **New Alloy scrape config** entry targeting the exporter's metrics endpoint
- **New Grafana dashboard** (`ai-usage.json`) provisioned via Terraform with stat panels for 5-hour window, 7-day window, OpenRouter credits, and usage-over-time graphs
- **New age-encrypted secrets** for the Codex OAuth token (extracted from `~/.pi/agent/auth.json`) and `chatgpt-account-id`, deployed to habiki

## Capabilities

### New Capabilities

- `ai-usage-metrics`: Prometheus exporter that polls Codex and OpenRouter APIs for usage data, exposes gauges for window percentages, credit balances, reset timers, and rate-limit status
- `ai-usage-dashboard`: Grafana dashboard displaying Codex 5-hour and 7-day window usage, OpenRouter credit balance, usage-over-time graphs, and rate-limit/status indicators, provisioned declaratively via Terraform

### Modified Capabilities

<!-- No existing capability requirements are changing -->

## Impact

- **Affected code**: New files only — `src/roles/nixos/files/etc/nixos/pkgs/ai-usage-exporter.py`, `src/roles/nixos/files/etc/nixos/modules/ai-usage.nix`, `terraform/dashboards/ai-usage.json`; modifications to `src/roles/nixos/files/etc/nixos/modules/alloy.nix` (new scrape target) and `terraform/grafana.tf` (new dashboard resource)
- **Secrets**: New `codex_oauth_token` and `chatgpt_account_id` values in `src/secrets.yml` and corresponding age-encrypted secrets in `src/roles/secrets/files/secrets/secrets.nix`
- **Dependencies**: Python `requests` and `prometheus_client` libraries (already available in the NixOS environment); no new external dependencies
- **Systems**: Exporter runs on habiki alongside existing Python exporters (GitHub observability, Frontier indexer chain head)
