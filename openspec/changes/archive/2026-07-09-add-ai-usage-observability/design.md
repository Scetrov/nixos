## Context

The NixOS infrastructure already has a mature observability pipeline: Python exporters → Alloy → Mimir → Grafana, with dashboards provisioned declaratively via OpenTofu. Two existing custom exporters (GitHub repository observability on port 9177, Frontier indexer chain head on port 9185) provide the exact architectural pattern to follow.

Two data sources need to be polled for AI usage metrics:

- **Codex (ChatGPT) usage windows**: The internal `https://chatgpt.com/backend-api/wham/usage` endpoint returns primary (5-hour) and secondary (7-day) window usage percentages, rate-limit status, and reset timers. Auth requires an OAuth Bearer token + `chatgpt-account-id` header from Pi's `~/.pi/agent/auth.json` (`openai-codex` key). This endpoint is the same one used by the official Codex CLI and by popular Pi extensions (`@narumitw/pi-codex-usage`, 4,500+ downloads/month).

- **OpenRouter credits**: The documented `https://openrouter.ai/api/v1/credits` endpoint returns `total_credits` and `total_usage`. Auth uses the existing `openrouter_api_key` already managed in `src/secrets.yml`.

## Goals / Non-Goals

**Goals:**
- Single Grafana dashboard showing Codex 5h window, 7d window, and OpenRouter credit balance in one view
- Usage-over-time graphs for trend visibility
- Rate-limit status indicators (allowed/limited)
- Reset countdown timers for both Codex windows
- Follow existing exporter/dashboard provisioning patterns exactly

**Non-Goals:**
- Per-session or per-model token breakdown (that's session-level data, not subscription window data)
- Cost in dollars (Codex subscription is time-window-based, not per-token; OpenRouter credits are the cost metric)
- Budget alerting or Grafana OnCall integration (future enhancement)
- Tracking Anthropic or other providers (not currently in use beyond DNS allowlist)
- Modifying Pi or its extensions (read-only consumption of existing auth.json)

## Decisions

### 1. Exporter runs on habiki with OAuth secret deployment (Option A)

**Choice**: Deploy the exporter as a systemd service on habiki, with the Codex OAuth token deployed as an age-encrypted secret.

**Rationale**: This follows the existing pattern (GitHub observability exporter, Frontier exporter both run as systemd services on habiki). The OAuth token from `auth.json` auto-refreshes; the exporter will handle token refresh itself using the `refresh_token` from the OAuth credential.

**Alternatives considered**:
- *Option B (run on workstation)*: Rejected. Workstation may sleep, creating metric gaps. No existing pattern for workstation-local exporters in the Alloy scrape config.
- *Option C (proxy via Pi extension)*: Rejected. Adds a Pi dependency to the infrastructure pipeline; metrics gap when Pi isn't running. Breaks the "infrastructure is declarative" principle.

### 2. OAuth token refresh in the exporter

**Choice**: The exporter reads the full OAuth credential from the age-encrypted secret file (access token, refresh token, expiry, token URL). On startup and when the access token is within 5 minutes of expiry, it POSTs to the token refresh URL to obtain a new access token. The refreshed token is held in memory only.

**Rationale**: Avoids the operational complexity of cron-based exporter restarts or periodic secret re-deployment. Standard OAuth client pattern. The auth.json already contains all fields needed for refresh.

**Alternatives considered**:
- *Restart exporter via systemd timer*: Rejected. Coarse-grained; metrics gap during restart; no benefit over in-process refresh.
- *Sync auth.json via agenix rekey*: Rejected. Requires external cron/timer orchestration; race condition if sync happens mid-refresh.

### 3. Single exporter for both data sources

**Choice**: One Python exporter polls both the Codex wham/usage endpoint and the OpenRouter /credits endpoint.

**Rationale**: Both data sources are lightweight HTTP GET calls with minimal processing. One process, one port, one scrape config. The OpenRouter API key is already available in the NixOS secrets infrastructure; the Codex OAuth token comes from a separate age-encrypted file.

**Alternatives considered**:
- *Two separate exporters*: Rejected. Unnecessary process overhead; both poll at the same interval; both belong to the same domain.

### 4. Terraform-provisioned dashboard with Grafana gauge thresholds

**Choice**: Dashboard provisioned as `terraform/dashboards/ai-usage.json`, following the existing 13-dashboard pattern. Stat panels use Grafana's built-in threshold coloring (green/yellow/red) based on usage percentage. Time-series panels use the existing Heart Pumps Neon palette from AGENTS.md.

**Rationale**: Declarative, version-controlled, no manual dashboard creation. Consistent with every other dashboard in the infrastructure. The palette is already defined and approved.

**Alternatives considered**:
- *Manual dashboard in Grafana UI*: Rejected. Violates IaC principle; no version control; lost on Grafana rebuild.

### 5. Exporter uses standard Prometheus client, metrics follow naming conventions

**Choice**: Metrics follow the pattern used by existing exporters (`snake_case` gauge names, `_percent` suffix for percentages, `_seconds` for durations).

**Metrics planned**:

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `ai_codex_window_used_percent` | Gauge | `window="5h\|7d"` | Percent of window used |
| `ai_codex_window_reset_seconds` | Gauge | `window="5h\|7d"` | Seconds until window reset |
| `ai_codex_limit_reached` | Gauge | — | 1 if rate-limited, 0 otherwise |
| `ai_codex_plan_type` | Info | `plan_type` | Subscription plan type |
| `ai_openrouter_credits_total` | Gauge | — | Total credits purchased |
| `ai_openrouter_credits_used` | Gauge | — | Credits consumed |
| `ai_exporter_scrape_success` | Gauge | `source="codex\|openrouter"` | 1 if last scrape succeeded |
| `ai_exporter_scrape_duration_seconds` | Gauge | `source="codex\|openrouter"` | Duration of last scrape |

## Risks / Trade-offs

- **[wham/usage endpoint is undocumented]**: The Codex usage endpoint is an internal ChatGPT backend API, not a documented public API. It could change or break without notice. → **Mitigation**: The Pi extensions ecosystem already depends on this endpoint; breakage would affect thousands of users and the official Codex CLI. Monitor the extension ecosystem for changes. If the endpoint changes, the fallback is `codex app-server --listen stdio://` → `account/rateLimits/read` RPC, which the `@narumitw/pi-codex-usage` extension already implements as a fallback path.

- **[OAuth token refresh failure]**: If the refresh token expires or is revoked, the exporter loses access to Codex metrics. → **Mitigation**: The exporter exposes `ai_exporter_scrape_success{source="codex"}` which drops to 0 on auth failure. Grafana stat panels show "N/A" when no data. Manual intervention: re-extract auth.json from workstation and re-deploy.

- **[Credential exposure]**: OAuth tokens grant access to the ChatGPT account and must be protected. → **Mitigation**: Token deployed as age-encrypted secret, readable only by the exporter's systemd service user (root or dedicated user). Never stored in Nix store. Follows the existing pattern for `hermes_webui_env` (contains `OPENROUTER_API_KEY`).

- **[Polling interval vs. freshness]**: The exporter polls every 60 seconds. Codex window usage can change rapidly during active sessions. → **Mitigation**: 60s is the same interval used by the Codex CLI and Pi extensions. It's sufficient for trend visibility. The dashboard is for awareness, not real-time enforcement.
