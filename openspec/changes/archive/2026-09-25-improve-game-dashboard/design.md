## Context

The declaratively provisioned `project-zomboid-service` Grafana dashboard currently plots `increase(...[1h])` as overlapping rolling-hour lines and presents a table from an instant `player_x` query. The former obscures activity density; the latter only shows coordinate series that still exist at the instant query time. The dashboard already uses the Grafana time range, managed Prometheus datasource, and native metrics with resettable `-today` totals.

## Goals / Non-Goals

**Goals:**

- Present native event totals as discrete bars, with Grafana choosing a practical interval for the current range (normally 5–15 minutes).
- Preserve player observations from throughout the selected dashboard range and reduce each player’s fields to the latest observation and timestamp.
- Show last-seen time plus health, days alive, and zombies killed only when supported native data exists.
- Keep unavailable data distinguishable from zero and retain a compact roster compatible with the existing player-path workflow.

**Non-Goals:**

- Persist a character directory, track players outside Prometheus retention, or infer player state from logs.
- Change Project Zomboid runtime metrics, expose RCON, add alerts, or add new external dependencies.
- Redesign the path/map panel beyond updating its roster context and selector wiring when necessary.

## Decisions

### Use interval-aligned `increase()` bars rather than fixed rolling windows

The event panel will be a Grafana bar-chart/time-series-bars visualization whose range queries use Grafana’s interval variable (with a minimum interval configured to keep buckets readable). Each event expression will calculate an increase over that same interval, producing non-overlapping bucket totals. Native daily resets remain counter resets under PromQL `increase()` semantics, and no sample remains unavailable rather than becoming zero.

A fixed `[1h]` selector was rejected because its overlapping windows misrepresent event timing. A hard-coded `[5m]` interval was rejected because it is too dense for longer dashboard ranges and too coarse for short investigations.

### Build the roster from range observations and reduce per player

The roster will query player series across the selected dashboard range in table form and use Grafana transformations to group by player identity, select each field’s latest value, and retain the observation timestamp as last seen. Health, days-alive, and zombies-killed metrics will be joined on the same player identity only where verified native series expose them. Missing per-field series will render as unavailable, not zero or a fabricated row value.

An instant `player_x` query was rejected because it excludes disconnected players. Maintaining roster state in a database or through a custom exporter was rejected as unnecessary scope and additional operational state.

### Verified telemetry contract

The managed Mimir datasource exposes resettable `connection` totals for `zombies-killed-today`, `burned-corpses-today`, and `players-killed-by-zombie-today`. Historical player coordinates expose stable `name` and `id` labels through `player_x` and `player_y`; native health, days-alive, and per-player zombies-killed series are not exposed. The roster therefore renders those three fields as `Unavailable` and does not infer them, or any absent event series, as zero.

### Bound roster scope to the dashboard time range

The roster title and description will explicitly state that it contains players observed in the active Grafana range, not a complete saved-character roster. The player selector/path panel will continue to use available native per-player labels and the dashboard range.

This avoids implying durable character history while giving GMs useful recent-player context.

## Risks / Trade-offs

- [Native player vitality/lifetime metrics have different names or are absent] → Verify available metric names and labels on the deployed datasource before finalizing expressions; omit unsupported fields and show unavailable values.
- [Range-query transformations cannot reliably join fields with inconsistent labels] → Join only on the verified stable player-identity label and retain the roster with the independently valid fields rather than guessing matches.
- [Very long dashboard ranges create too many roster observations or bars] → Use Grafana’s adaptive interval and minimum interval, then validate rendering at common short and long ranges.
- [Counter reset or sparse telemetry confuses a bucket] → Retain `increase()` semantics and explicit unavailable messaging; do not replace absent samples with zero.

## Migration Plan

1. Validate native event and per-player metric names, labels, and sample behavior against the managed Prometheus datasource.
2. Update the versioned dashboard JSON and deploy through the existing declarative Grafana provisioning workflow.
3. Inspect the rendered dashboard over short, normal, and long time ranges, including a disconnected player observed earlier in the range.
4. Roll back by restoring the prior dashboard JSON and reprovisioning if expressions or transformations render incorrectly.

## Open Questions

- Which exact native metric names and labels expose player health, days alive, and zombies killed on the deployed Build 42 server?
- What minimum interval yields 5–15 minute event buckets for the dashboard’s usual time ranges after Grafana interval calculation?
