## Why

Home Assistant on Habiki is deployed as a plain container, so the built-in Supervisor add-on path for Matter is unavailable. As a result, enabling Matter prompts for `ws://localhost:5580/ws`, but nothing is listening there and Matter commissioning cannot start.

## What Changes

- Add a declarative Matter Server deployment on Habiki for the existing Home Assistant container-based installation.
- Configure the deployment so Home Assistant can reach the Matter websocket endpoint at `ws://localhost:5580/ws` on the Habiki host.
- Persist Matter server state and required runtime configuration through the existing NixOS module workflow instead of manual UI-only setup.
- Document the separation between Matter Server and Thread border router responsibilities so Thread requirements are handled explicitly.
- Add deployment and runtime verification steps for the Matter websocket endpoint, Home Assistant connectivity, and post-deploy logs.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `home-assistant-platform`: extend the platform requirements to cover a declarative Matter Server backend for the container-based Home Assistant deployment on Habiki.

## Impact

- Affects `src/roles/nixos/files/etc/nixos/modules/home-assistant.nix` and `src/roles/nixos/files/device-configuration/habiki.nix`.
- Adds a managed Matter Server runtime on Habiki, including persistent state and Home Assistant endpoint expectations.
- Extends the `home-assistant-platform` OpenSpec requirements and deployment verification for Matter support.
- May require additional documentation of Thread border router ownership, but does not require a second Home Assistant instance.
