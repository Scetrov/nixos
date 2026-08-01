## Context

The Codex app-server migration replaced provider-slot labels with semantic duration-derived labels and the current account supplies only `window="weekly"`. The dedicated AI Usage dashboard was migrated with authentication, scrape-success, window-presence, and freshness gates. The Operations Platform Overview was not: its two Codex cards still query `window="5h"` and `window="7d"` without gating.

Alloy continues to scrape the unchanged exporter endpoint at `127.0.0.1:9188` and remote-write the metrics to Mimir. The required weekly usage, reset timestamp, authentication, scrape-success, last-success, poll-interval, and window-presence series already exist in Mimir.

## Goals / Non-Goals

**Goals:**

- Surface remaining weekly Codex allowance and its next reset time in the Operations Platform Overview.
- Prevent absent, stale, failed, or explicitly unauthenticated Codex data from appearing current.
- Reuse the established metric semantics, freshness threshold, Mimir datasource, and Heart Pumps Neon palette.
- Add regression coverage for this second Grafana presentation of Codex data.

**Non-Goals:**

- Change exporter, app-server, Alloy, Mimir, or OpenRouter behavior.
- Add Grafana alerts, notification policies, new credentials, routes, or listeners.
- Show speculative 5-hour, 7-day, or other windows when the provider has not returned them.
- Redesign unrelated Operations Platform Overview cards.

## Decisions

### Replace the two legacy cards in place

The two existing adjacent Codex card positions will become `Weekly Remaining` and `Weekly Reset`. Retaining their positions preserves the overview layout while changing the content from retired provider labels to operator-relevant weekly information.

Creating a separate section or duplicating the detailed AI Usage health panels was considered and rejected: the overview needs an at-a-glance allowance and reset summary, while the dedicated dashboard remains the place for trends and diagnostics.

### Use freshness-gated weekly PromQL expressions

`Weekly Remaining` will calculate `100 - ai_codex_window_used_percent{window="weekly"}`. `Weekly Reset` will calculate `clamp_min(ai_codex_window_reset_timestamp_seconds{window="weekly"} - time(), 0)` and render it as a duration.

Both expressions will be joined with the established predicates for `ai_codex_authenticated == 1`, `ai_exporter_scrape_success{source="codex"} == 1`, a present weekly window, and a last-success age no greater than two Codex poll intervals. When any predicate is false or a required series is absent, Grafana will render `N/A` rather than last-known quota data.

Using bare weekly metrics was rejected because the exporter intentionally retains samples across a failed source poll, which can otherwise make obsolete values look current. Reusing the fixed `5h` or `7d` labels was rejected because those labels are no longer part of the exporter contract.

### Preserve visual semantics

The remaining-allowance stat will retain the approved capacity colors: pink for low remaining allowance, amber for the midpoint, and teal for healthy capacity. The reset card will use the dashboard’s standard dark-mode-compatible styling and a duration unit. Both panels will continue using the Mimir datasource.

### Validate both dashboard presentations

The dashboard test suite will continue checking the detailed AI Usage dashboard and will add targeted assertions for the Operations Platform Overview: panel titles, semantic weekly queries, freshness and authentication guards, reset calculation and duration unit, datasource, palette, and absence of fixed `5h`/`7d` labels. This is preferable to a manual-only check because the original migration validated only the dedicated dashboard, permitting this drift.

## Risks / Trade-offs

- **[A future account has no weekly window]** → The presence predicate produces `N/A`; operators can use the detailed dashboard to inspect actual returned windows rather than seeing fabricated capacity.
- **[A source failure retains old Prometheus samples]** → Scrape-success and two-poll freshness predicates suppress the cards.
- **[PromQL differs from the established dashboard gate]** → Reuse the detailed dashboard’s predicate structure and validate it in tests.
- **[A reset timestamp is malformed or already elapsed]** → The exporter rejects malformed values; `clamp_min` prevents negative display durations.

## Migration Plan

1. Update the two Operations Platform Overview panel definitions and dashboard tests.
2. Run JSON parsing, dashboard unit tests, and OpenTofu formatting/validation through the repository-approved wrapper.
3. Apply the dashboard with `scripts/tofu.sh` and verify fresh weekly remaining allowance and reset duration in Grafana.
4. Verify an unauthenticated, failed, stale, or weekly-window-absent state renders `N/A`.
5. Roll back by restoring the prior dashboard JSON through `scripts/tofu.sh`; this restores the legacy layout but not meaningful data for a weekly-only account.

## Open Questions

- None; the overview purpose and metric semantics are defined by the completed app-server migration and the operator’s requested two values.
