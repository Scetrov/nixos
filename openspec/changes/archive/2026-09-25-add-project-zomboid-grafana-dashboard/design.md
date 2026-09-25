## Context

Project Zomboid Build 42 runs as `project-zomboid.service` on Habiki. The service deliberately disables RCON and is controlled locally through a private FIFO. Alloy sends the system journal to Loki and supplies Unix host telemetry to Mimir; Grafana dashboards and the service catalog are declared in `terraform/dashboards` and `terraform/grafana.tf`.

The server needs a shared operator/game-master view. The selected scope is native server telemetry only: no client software, no RCON, no alert rules, and no character health or inventory data. The exact Build 42 native Prometheus metric names, labels, bind behavior, and coverage are not yet validated against the deployed server.

## Goals / Non-Goals

**Goals:**

- Expose the native Build 42 Prometheus endpoint only on a private local path and scrape it into the existing Prometheus/Mimir telemetry flow.
- Correlate Project Zomboid metrics and journal logs using stable `service="project-zomboid"` and `host` identities.
- Provide an `Operations / Services` dashboard that makes playability, world activity, game runtime resources, and operational evidence quickly understandable.
- Provide a roster and selected-player live-path map as a half-width GM detail panel when native coordinates are emitted.
- Truthfully distinguish observed values, unavailable telemetry, and zero values.

**Non-Goals:**

- Enable, expose, or otherwise depend on RCON.
- Install client-side monitoring, derive client rendering FPS, or collect player character health, inventory, or other saved-character detail.
- Add automated alert rules or modify notification routing.
- Show host-wide CPU or memory panels in the Project Zomboid dashboard; the dashboard focuses on game/JVM or service-cgroup resource use and links to existing platform views for host context.
- Guarantee native animal or server tick-rate telemetry before it is confirmed on the installed Build 42 release.

## Decisions

### Use native Build 42 Prometheus telemetry as the game source

The server JVM will be configured to expose its native endpoint on a private local listener, and the repository's established scrape and remote-write path will ingest it. This preserves the current access model and needs no user/client installation.

The alternative, `pzmonitor`, supplies richer RCON-derived FPS and animal data but conflicts with the existing no-RCON design and would add a third-party dependency and secret. A custom parser of private-console output would preserve no-RCON but is a less reliable bespoke collector. Neither is included in this change.

### Verify telemetry before defining final queries

Implementation begins by running the actual enabled Build 42 endpoint locally and recording metric names, labels, scrape behavior, and listener bind address. Dashboard queries are derived from that result rather than from community examples. The deployment must not open a TCP listener to LAN, Headscale, or WAN.

Panels for a requested signal are only added when the native endpoint emits an unambiguous value. The dashboard's Signal Coverage text identifies absent signals (such as animal instances or server tick rate) as unavailable. It must not represent absence as zero or substitute a different semantic counter.

### Keep game process resources distinct from host resources

The resource row shows JVM memory and service/game CPU or memory telemetry attributable to `project-zomboid.service`. If the existing telemetry path cannot provide sound per-service cgroup metrics, implementation must onboard a narrowly scoped, locally scraped cgroup/systemd source or explicitly leave the unavailable signal documented. Host-wide resource panels remain in the established System Resources dashboard, reached through a link.

This reflects the requested game-only view and avoids falsely attributing other Habiki workloads to the game.

### Use a layered hybrid dashboard layout

The default six-hour, 30-second service-dashboard experience follows portal conventions, with a short top-level playability row, then world pulse, game runtime, GM detail, and evidence rows.

```
Playability:  server up | telemetry freshness | players | FPS/tick rate | update time | JVM heap
World pulse:  zombies by native semantic | animals if available | cells | daily events
Game runtime: game/service CPU and memory | JVM runtime | network indicators if available
GM detail:    roster/table (12 columns) | selected-player live path map (12 columns)
Evidence:     warning/error logs | full recent logs | links to platform views
```

The map is a half-width panel sized approximately to the installed game map's 19968:16128 aspect ratio and uses a compact player selector. The native Geomap legend cannot dynamically show player names as independently toggleable colour keys; keep the selector rather than introducing a custom plugin. A missing roster value reads Unavailable, and the map contains no player marker; no redundant separate empty-state panel is needed. The roster/map row does not contain character health or inventory fields.

The Geomap basemap MUST be the installed Build 42 **game-world** map, not an Earth basemap. Generate a private XYZ tile pyramid from Habiki's installed `worldmap.png` or `pyramid.zip`, pinning any build-time tooling via the existing Nixpkgs input. Serve those static tiles beneath Grafana's `/grafana/` URL prefix through Caddy, checking the existing Grafana user or renderer service-account identity via `/grafana/api/org` (no new listener, no map assets committed to git). The original separate Authentik outpost route redirected browser tile requests to login and must not be used. Project native `player_x` and `player_y` from world-tile coordinates into the matching tile projection; do not use the game's `player_lat` and `player_lon` directly unless their transform is proven to align. Verify tile dimensions, coordinate bounds, and visible landmark/player alignment before calling the map complete.

Healthy/current status uses teal, degraded/reference conditions amber, failures pink, and population/world-state series the approved purple/magenta support colors. Give concurrently plotted series distinct colours and short keys. Population labels retain the source's loaded/simulated/total semantics. The game-day event gauges reset with the game day; display approximate rolling-hour increases using PromQL `increase(...[1h])`, not raw `-today` totals described as hourly rates. Hide detailed signal notes in a collapsed More info row, and use value-only stat rendering so metric selectors do not crowd the overview.

### Enable visual validation with Grafana's supported renderer service

Grafana 13 does not load the retired in-process image-renderer plugin. To validate the GM map and empty states using a repeatable snapshot, run the SHA256-pinned NixOS `grafana-image-renderer` service on Habiki loopback with a vault-backed token shared with Grafana at runtime. The Chromium browser calls back through the existing authenticated HTTPS `/grafana/` origin so its game-map tile requests reach Caddy (a direct localhost callback bypasses Caddy and returns 404 for map tiles); cap concurrent renders to one because Habiki has limited memory headroom. No external renderer port or new notification route is introduced.

### Correlate logs declaratively

Alloy journal relabeling will map `project-zomboid.service` to `service="project-zomboid"` while retaining `host`. The dashboard provides a focused warning/error view and a full chronological logs view. Dashboard provisioning, registration, and catalog linking remain source-controlled in the Terraform Grafana workflow.

## Risks / Trade-offs

- [Native endpoint lacks a requested metric] → Validate before building panels; mark the signal unavailable and avoid RCON as an implicit fallback.
- [Endpoint binds beyond localhost] → Verify listening address before deployment completion; bind or constrain it to a private local path and do not add firewall exposure.
- [A geographic basemap misrepresents the game world] → Use only tiles rendered from the installed Build 42 map, convert game world X/Y against the same tile projection, and verify alignment; never fall back to Earth tiles.
- [Player labels/coordinates create high-cardinality or sensitive views] → Limit the dashboard to the operator/GM audience, show only online roster/map data, and avoid saved-character metrics.
- [No trusted per-service CPU metric exists in current telemetry] → Verify cgroup metric availability first; onboard a narrowly scoped local collector only if it preserves attribution and security boundaries.
- [Game counters are loaded rather than global world population] → Preserve native semantics in title, legend, and Signal Coverage text.
- [Dashboard changes made through Grafana UI drift] → Keep JSON and Terraform registration as the sole source of truth.

## Migration Plan

1. Capture the local native endpoint's metrics, labels, listener behavior, and supported player coordinate data on Habiki.
2. Add private endpoint configuration and the required scrape/relabel configuration, then verify local scrape and retained Mimir ingestion.
3. Add the Project Zomboid journal service identity and verify Loki queries with both `service` and `host` labels.
4. Add the dashboard, service-catalog entry, and Terraform registration through the declarative workflow.
5. Deploy using the targeted NixOS and Grafana/OpenTofu workflows for Habiki, validate dashboard panels and map empty states, and verify that no new public listener exists.

Rollback removes the dashboard registration and telemetry configuration, then redeploys the same targeted workflows. It does not affect game state or re-enable RCON.

## Open Questions

- Which exact native metric names and labels are emitted by the installed Build 42 server for tick rate/FPS, animals, zombies, process resources, network, players, and coordinates?
- Can the native endpoint bind directly to loopback, or is an additional local-only containment mechanism required?
- Which existing or minimally added cgroup/systemd telemetry source can provide trustworthy `project-zomboid.service` CPU usage without host-wide substitution?
