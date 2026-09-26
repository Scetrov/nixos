## Context

The declaratively managed Project Zomboid dashboard currently turns three Build 42 native `connection` game-day gauges into reset-aware, discrete interval bars: total zombies killed, burned corpses, and players killed by zombies. A live read-only review of Habiki's private `127.0.0.1:9105/metrics` endpoint verified four additional daily event gauges:

- `zombies-killed-by-fire-today`
- `players-killed-by-fire-today`
- `players-killed-by-player-today`
- `zombified-players-today`

The native exporter declares `connection` as a gauge, and these values reset at the game-day boundary. They are not Prometheus counters despite their monotonic-within-game-day behavior. The endpoint also verifies native `player_x`, `player_y`, `id`, and `name` labels, but does not expose player health, days alive, or individual zombie kills. The endpoint must remain loopback-scraped and private; RCON stays disabled.

## Goals / Non-Goals

**Goals:**

- Show each verified additional daily event total as a discrete, reset-aware event count using the dashboard-selected interval and its existing five-minute minimum.
- Retain the established event panel semantics: absent telemetry is unavailable, and game-day resets never produce negative values.
- Make overlap explicit: `zombies-killed-by-fire-today` is a subset of `zombies-killed-today`, not a separate additive total.
- Document the complete verified daily-event inventory for future dashboard maintenance.
- Present only verified player-roster fields and include both native World X and World Y coordinates.

**Non-Goals:**

- Add non-event gauges (world population, player count, performance, network, JVM, or pool metrics) to this chart.
- Derive game events from logs, deploy an exporter, add recording rules, alerts, or RCON.
- Change scrape routing, retention, dashboard layout outside the event and roster panels, or the dashboard's existing time-range/bucket selection policy.

## Decisions

### Use the four additional `connection` `-today` gauges

The dashboard will add one `increase(connection{parameter="..."}[$__interval])` query for each verified daily event gauge. They share the existing signal family, reset behavior, and gameplay-oriented unit, making them appropriate for one interval-event visualization.

Alternatives considered:

- **JVM GC counts or started threads:** technically interval-derivable counters but operational-runtime activity rather than in-game events; retain these for runtime troubleshooting rather than mixing units in the gameplay chart.
- **Network bytes, packets, and messages:** useful traffic signals but not gameplay events and several are sampled gauges; retain them in the network panel.
- **World, player, zombie, animal, and pool values:** these are occupancy or state gauges, not counts of actions during an interval.

### Keep total zombie kills and fire kills visually non-additive

The panel will continue to show total zombie kills and add a clearly named fire-kill series whose label/description states it is included in the total. The bars will remain individually rendered rather than stacked, preventing users from reading the subset as an additional total.

Alternative considered: replace total kills with fire kills. This would lose the primary total activity signal and omit non-fire kills, so it is rejected.

### Present verified player-roster coordinates without placeholders

The roster will query `player_x` and `player_y`, outer-join their timestamped observations, and group them by native player `id` and `name` to retain each player's latest World X and World Y. It will retain the native Player ID and last-seen time, and remove columns for health, days alive, and individual zombie kills because the endpoint does not emit these values.

Alternatives considered:

- **Keep placeholder columns labelled Unavailable:** this repeats a known endpoint limitation in every roster row and obscures useful coordinate space; remove the columns instead.
- **Infer status from aggregate game totals or logs:** those signals are not per-player status telemetry and would be misleading.

### Reuse reset-aware `increase()` and the current dashboard interval policy

Although the endpoint declares these as gauges, each `-today` value is a game-day cumulative total. PromQL `increase()` handles its reset boundary and yields each selected bucket's activity, consistent with the existing three series. The panel's five-minute minimum remains in place to avoid low-sample and visually noisy buckets.

Alternative considered: use subtraction between samples. This would yield negative values at a game-day reset and would duplicate the reset handling already provided by PromQL.

### Preserve series availability semantics

No `or vector(0)`, coercion, or synthetic data will be added. A series without samples remains Unavailable, which distinguishes missing/unsupported telemetry from an observed zero event count.

## Risks / Trade-offs

- [Game-day gauge resets and sparse scrapes can make a small interval estimate imperfect] → use existing `increase()` semantics and five-minute minimum; retain its approximate-interval description.
- [Seven bar series can reduce legibility] → use distinct approved palette colours, concise legends, and an explicit description of the zombie-fire subset; validate the rendered panel at normal and long time ranges.
- [Native exporter parameters can change across Build 42 updates] → pin dashboard queries to the live-verified names and update the telemetry contract; verify endpoint output before accepting a game-server upgrade.
- [All newly observed values were zero during the read-only review] → validate query presence and rendering even when values are zero, then confirm nonzero behavior only during normal gameplay without generating artificial deaths or fires.
- [Coordinate frames can join into partial duplicate rows] → use Grafana's outer join mode and render the live roster after deployment to confirm one complete row per observed player.

## Migration Plan

1. Update the dashboard JSON and telemetry contract in source control.
2. Validate JSON and the declarative Grafana configuration, then apply through the established targeted automation path.
3. Render or inspect the dashboard at short and long ranges to confirm the seven series, interval bars, legends, colours, and unavailable handling.
4. Roll back by restoring the prior dashboard JSON and applying the same declarative workflow; no game-server state, scrape configuration, or database migration is involved.

## Open Questions

- None. The endpoint review verified the additional parameter names and their shared `connection` gauge type.
