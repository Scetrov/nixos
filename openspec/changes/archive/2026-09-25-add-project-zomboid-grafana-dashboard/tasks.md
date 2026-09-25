## 1. Validate native Build 42 telemetry contract

- [x] 1.1 Enable the native endpoint in a controlled local test of the installed Project Zomboid Build 42 server and capture its metric names, labels, scrape response, player-coordinate coverage, and listener address.
- [x] 1.2 Record which requested signals are actually available (server/tick rate, player count, zombies by semantic category, animal instances, loaded cells, events, JVM/runtime, and network) and define exact dashboard semantics for each supported signal.
- [x] 1.3 Verify that the endpoint is private to Habiki and that the validation does not enable RCON, introduce a RCON secret, or require client software.
- [x] 1.4 Identify and validate a trustworthy game/JVM or `project-zomboid.service`-attributable CPU and memory metric source; document unavailable signals rather than using host-wide substitutes.

## 2. Onboard private Project Zomboid telemetry

- [x] 2.1 Update the Project Zomboid NixOS service configuration to enable the verified native metrics endpoint while preserving the current private-control and no-RCON security boundaries.
- [x] 2.2 Add the verified private scrape target, stable `service="project-zomboid"` and `host` labels, and retained Mimir-compatible ingestion through the existing telemetry pipeline.
- [x] 2.3 Add or configure only the narrowly scoped local cgroup/systemd telemetry needed for verified game-attributable resource metrics, if the existing path cannot provide them.
- [x] 2.4 Add Alloy journal relabeling for `project-zomboid.service` and verify focused Loki queries retain both Project Zomboid service and Habiki host identity.
- [x] 2.5 Add automated configuration tests that assert native telemetry is private, RCON remains disabled, and Project Zomboid metric/log labels follow the observability contract.

## 3. Build the hybrid service dashboard

- [x] 3.1 Create the declarative `svc-project-zomboid` dashboard JSON with portal navigation, six-hour/30-second service-dashboard defaults, a Signal Coverage panel, and the approved Grafana color semantics.
- [x] 3.2 Add playability and world-pulse panels using only validated native metrics; preserve loaded/simulated/total meanings and render unsupported requested signals as unavailable rather than zero.
- [x] 3.3 Add game/JVM or service-cgroup CPU and memory panels without presenting host-wide resource measurements as game consumption, with a link to the existing System Resources dashboard for host context.
- [x] 3.4 Add an online-player roster and a selected-player path geomap over authenticated Build 42 game-world tiles in a half-width panel, converting native world X/Y to tile coordinates, showing unavailable roster data when no player is online and excluding character health and inventory detail.
- [x] 3.5 Add focused warning/error and full chronological Loki log panels filtered by `service="project-zomboid"`.
- [x] 3.6 Register the dashboard in Terraform under `Operations / Services` and add its accurate signal-coverage entry to the declarative Operations Service Catalog.
- [x] 3.7 Add dashboard structure/query tests that validate datasource UIDs, stable identities, half-width map layout, no fake zero-value fallbacks, and absence of alert-rule resources.

## 4. Validate and deploy

- [x] 4.1 Run Nix evaluation and the affected Project Zomboid/dashboard tests; parse and validate all changed dashboard JSON and Terraform configuration through the repository's approved tooling.
- [x] 4.2 Deploy the NixOS telemetry changes with a targeted Habiki `nixos` run and verify the private endpoint, Prometheus scrape health, Mimir retention, Loki labels, and absence of externally reachable new listeners.
- [x] 4.3 Apply the Grafana dashboard changes through `scripts/tofu.sh`, then verify the service-catalog link, panel data/empty states, player map behavior when supported, and logs in Grafana.
- [x] 4.4 Confirm that no RCON listener, RCON secret, client dependency, automated alert rule, notification policy, or character health/inventory telemetry was introduced.
- [x] 4.5 Install Grafana's loopback-only image-renderer service declaratively with a vault-backed shared token and bounded concurrency; verify the dashboard renders and inspect the selected-player map snapshot.

## 5. Refine the game rules and operational dashboard

- [x] 5.1 Reconcile 100 free character-creation points and enabled multi-hit in the existing Build 42 sandbox without replacing other settings or saved world data; validate and deploy the targeted NixOS change.
- [x] 5.2 Collapse detailed notes, simplify stat readouts, distinguish graph keys, and derive rolling-hour game events from resettable native daily totals.
- [x] 5.3 Remove redundant location and empty-state panels; keep the compact player selector and resize/frame the half-width Build 42 map close to the world-map aspect ratio.
- [x] 5.4 Validate game configuration, dashboard queries/layout, deployed settings, and an inspected full-dashboard screenshot; document the native Geomap legend limitation.
