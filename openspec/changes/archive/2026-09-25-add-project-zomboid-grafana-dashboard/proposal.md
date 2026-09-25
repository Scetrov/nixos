## Why

Project Zomboid is operated as a persistent Build 42 server, but its game health, world activity, resource consumption, and service logs are not yet available together in the declarative Grafana operations portal. Operators and game masters are the same people, so they need one trustworthy view that answers whether the server is playable and provides controlled player/world context when it is.

## What Changes

- Enable and privately scrape the Build 42 native Prometheus endpoint for the Project Zomboid server without enabling RCON or requiring client-side software.
- Add a stable Project Zomboid service identity to Loki journal logs and retain host correlation.
- Add a declaratively managed `Project Zomboid Server` dashboard under `Operations / Services`, including playability, native game/world telemetry, game-process resource telemetry, and Loki log views.
- Provide a player roster and compact-selector player-path map as a half-width GM detail panel, using only native telemetry available from the server.
- Reconcile Build 42 sandbox settings for 100 free character-creation points and multi-hit melee combat, preserving the existing world and other settings.
- Explicitly describe telemetry availability and semantics; unavailable native signals (including animal counts or tick rate, if absent) SHALL be shown as unavailable rather than inferred or represented as zero.
- Add the dashboard to the declarative service catalog. This change does not add alert rules, RCON, client telemetry, or character health/inventory data.

## Capabilities

### New Capabilities
- `project-zomboid-observability`: Private native game telemetry, service log correlation, and a hybrid operator/game-master dashboard for the Project Zomboid server.

### Modified Capabilities
- `grafana-operations-portal`: Register and catalog the Project Zomboid service dashboard within the existing source-controlled operations portal.

## Impact

- Affected NixOS modules: `project-zomboid.nix`, `alloy.nix`, and the metrics scrape configuration as required by the native endpoint.
- Affected Grafana source of truth: `terraform/dashboards`, `terraform/grafana.tf`, and the service catalog dashboard.
- The dashboard will use the existing Prometheus/Mimir and Loki datasources and the `service`/`host` correlation model.
- Native metric names, labels, listener bind behavior, and the availability of FPS/tick-rate and animal metrics must be verified on the deployed Build 42 server before final panel queries are accepted.
