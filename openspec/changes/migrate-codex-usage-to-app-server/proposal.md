## Why

Habiki's AI usage exporter can no longer refresh its expired Codex OAuth credential, and its fixed assumption that Codex always returns a 5-hour primary window plus a 7-day secondary window no longer matches the current weekly-only response. The integration must move behind the upstream Codex app-server so OAuth rotation and provider schema changes are handled by Codex while Grafana continues to receive accurate, freshness-aware usage data.

## What Changes

- Run a pinned Codex app-server on Habiki as a declaratively managed Podman workload with a dedicated identity, persistent protected state, and a local Unix-socket interface.
- Bootstrap a dedicated ChatGPT managed login for the service and define backup, recovery, and reauthentication behavior for mutable OAuth state.
- Change the AI usage exporter to obtain Codex rate limits from `account/rateLimits/read` instead of refreshing OAuth and polling the private `wham/usage` endpoint directly.
- Normalize returned windows by their reported duration, support a single weekly window, and never synthesize zero-valued metrics for absent windows.
- Add last-success and data-freshness telemetry so cached values cannot be mistaken for current usage.
- Update the Grafana dashboard to present weekly remaining usage, weekly consumed usage, reset time, authentication/scrape health, and stale-data behavior.
- Add automated coverage for app-server protocol handling, weekly-only responses, missing windows, reset timestamps, authentication failures, and metric exposition.
- **BREAKING**: Retire the fixed `window="5h"` and `window="7d"` Codex metric series and replace them with duration-derived semantic window labels such as `window="weekly"`.
- Keep the existing OpenRouter collection and dashboard behavior out of scope except where shared exporter health plumbing must remain compatible.

## Capabilities

### New Capabilities
- `codex-app-server-runtime`: Declarative, isolated Codex app-server operation on Habiki, including local transport, managed ChatGPT authentication, persistent credential state, recovery, and service health.

### Modified Capabilities
- `ai-usage-metrics`: Replace direct private-endpoint OAuth polling and fixed 5-hour/7-day assumptions with app-server rate-limit collection, duration-aware windows, and freshness telemetry.
- `ai-usage-dashboard`: Replace fixed 5-hour/7-day panels with weekly usage and reset panels that suppress stale values and expose provider health.

## Impact

- NixOS service/container configuration on Habiki and its package/image pinning.
- `src/roles/nixos/files/etc/nixos/pkgs/ai-usage-exporter.py` and its test coverage.
- Alloy/Mimir metric series and any PromQL consumers of the retired `5h` and `7d` labels.
- `terraform/dashboards/ai-usage.json` and its freshness-gated PromQL consumers.
- Age/Vault bootstrap secret handling, protected mutable service state, and the operational BCDR/reauthentication runbook.
- Existing `ai-usage-metrics` and `ai-usage-dashboard` OpenSpec contracts.
