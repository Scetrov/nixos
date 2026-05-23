# Home Assistant Matter Server Tasks

## 1. Matter Runtime Definition

- [x] 1.1 Choose the official Matter Server runtime form that this repository can deploy reliably on NixOS, and record the required port, state path, and permissions.
- [x] 1.2 Extend `src/roles/nixos/files/etc/nixos/modules/home-assistant.nix` with a `scetrov.services.home-assistant.matter.enable` option.
- [x] 1.3 Declare the Matter Server runtime only when the Matter option is enabled and ensure it serves `ws://localhost:5580/ws` on the Habiki host.
- [x] 1.4 Add persistent host-managed state for the Matter server with permissions that keep runtime artifacts out of Git.

## 2. Habiki Assignment And Boundaries

- [x] 2.1 Enable `scetrov.services.home-assistant.matter.enable = true;` in `src/roles/nixos/files/device-configuration/habiki.nix`.
- [x] 2.2 Ensure the Matter websocket is kept local-only and is not exposed through Caddy, Authentik, or any new public route.
- [x] 2.3 Update repository-managed Home Assistant documentation or audit notes to state that Matter Server and Thread border-router responsibilities are separate.

## 3. Validation

- [x] 3.1 Run focused validation for the changed Nix and OpenSpec files using the repository's established checks.
- [x] 3.2 Deploy narrowly with `./scripts/play.sh --limit habiki --tags nixos` and confirm both Home Assistant and the Matter server runtime are active.
- [x] 3.3 Verify on Habiki that port `5580` is listening and that the Matter websocket endpoint is reachable for Home Assistant at `ws://localhost:5580/ws`.
- [x] 3.4 Enable or re-test the Matter integration in Home Assistant and confirm it connects without requiring a second Home Assistant instance.
- [x] 3.5 Review Home Assistant and Matter server logs after deployment and record any remaining Thread border-router prerequisite before commissioning Thread-based Matter devices.
