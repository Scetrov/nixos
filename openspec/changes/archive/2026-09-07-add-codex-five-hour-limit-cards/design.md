## Context

The local AI usage exporter already normalizes provider-reported 300-minute and 10,080-minute Codex windows as `window="5h"` and `window="weekly"`, respectively. It emits per-window used percentage, reset timestamp, duration, and presence metrics, and preserves last-known values after a failed poll. Both existing dashboards therefore use authentication, scrape-success, window-presence, and a two-poll freshness gate before showing a current quota value.

The detailed AI Usage dashboard currently has weekly remaining and reset cards, while its historical trend is already generic and will show a returned five-hour series. The Operations Platform Overview similarly reserves two cards for weekly remaining and reset. The new provider response makes a short-horizon card pair operationally meaningful.

## Goals / Non-Goals

**Goals:**

- Display 5-hour and weekly remaining allowance plus reset countdowns in both dashboard presentations.
- Keep the two window types semantically distinct and only display a 5-hour value when the exporter reports that actual window.
- Preserve `N/A` behavior for absent, stale, failed, or unauthenticated Codex data.
- Retain declarative dashboard provisioning, Mimir queries, and the approved Heart Pumps Neon capacity palette.

**Non-Goals:**

- Change app-server rate-limit collection, exporter normalization, polling, Alloy, Mimir, OpenRouter, authentication, or alerting.
- Infer a 5-hour allowance from weekly data or create a placeholder series.
- Display the obsolete `7d` label, account-specific numeric quotas, or provider message-count estimates.

## Decisions

### Represent both real semantic windows as paired current-value cards

Each dashboard will show four Codex cards: 5-hour remaining, 5-hour reset, weekly remaining, and weekly reset. The detailed AI Usage dashboard will reorganize its top-level stat layout to accommodate the four cards while preserving its existing OpenRouter and health content. The Platform Overview will reorganize its capacity row so all four Codex values remain visible at a glance.

Showing only the detailed dashboard was rejected because the five-hour window is a near-term operational constraint and the overview is meant to surface such capacity. Replacing the weekly reset card with a five-hour card was rejected because reset timing is needed to interpret both limits.

### Reuse per-window freshness-safe PromQL gates

For each window label `W`, remaining allowance will be calculated as `100 - ai_codex_window_used_percent{window="W"}` and reset time as `clamp_min(ai_codex_window_reset_timestamp_seconds{window="W"} - time(), 0)`. Each expression will require all of:

- `ai_codex_authenticated == 1`;
- `ai_exporter_scrape_success{source="codex"} == 1`;
- `ai_codex_window_present{window="W"} == 1`; and
- collection age no greater than `2 * ai_exporter_poll_interval_seconds{source="codex"}`.

Using bare window gauges was rejected because retained Prometheus samples can falsely appear current after collection fails. The established global rate-limit status remains separate because the app-server provides a snapshot-level reached classification rather than a per-window state.

### Keep semantic labels, not provider slots or synthetic limits

Dashboard queries will use only `5h` and `weekly` semantic labels, matching the exporter’s duration normalization. The `5h` cards must show `N/A` if the 300-minute window is absent even if the weekly window is fresh. The generic detailed-dashboard usage trend remains the source for any future duration-derived labels.

Hardcoding provider primary/secondary slots, relabeling a window by position, and emitting an inferred five-hour value were rejected because the provider can omit or reorder windows.

### Validate layout and query contracts in dashboard tests

Tests will cover the four card titles, units, per-window expressions, presence and freshness gates, use of the Mimir datasource, approved colors, and continued absence of `7d`. Existing assertions that reject `5h` will be replaced with assertions that require it only in the intended current-value cards.

## Risks / Trade-offs

- **[Provider omits the 5-hour window for an account or changes limits]** → Presence-gated queries display `N/A`; the generic detailed trend continues to show only actual provider windows.
- **[A failed provider poll leaves old quota samples in Mimir]** → Scrape-success and two-poll freshness gates suppress all current-value cards.
- **[Four cards make the overview denser]** → Retain card pairs and compact stat sizing rather than hiding reset information or displacing unrelated observability content.
- **[The provider changes the 300-minute duration]** → The exporter emits a duration-derived label; no card claims it is a five-hour limit until a separately reviewed change maps that duration.

## Migration Plan

1. Update both dashboard JSON definitions and dashboard-unit assertions.
2. Validate JSON and run the relevant dashboard and exporter test suites.
3. Format and validate OpenTofu only through `scripts/tofu.sh`.
4. Apply via `scripts/tofu.sh`, then verify all four cards against a fresh authenticated response containing both windows and verify `N/A` for absent/stale/failed states.
5. Roll back by restoring the previous dashboard JSON via `scripts/tofu.sh`; the exporter and collected metrics remain unchanged.

## Open Questions

- None. The exporter fixture and normalization contract establish the exact semantic labels and the requested Option A scope establishes that both dashboard presentations show both windows.
