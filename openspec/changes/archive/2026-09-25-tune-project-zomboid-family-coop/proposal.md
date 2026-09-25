## Why

Habiki's private Build 42 server already grants generous character-creation points and multi-hit, but PvP remains enabled, the minimap and teammate locations are hidden, and new characters lack the requested supplies. A small, declarative co-op profile will reduce accidental harm and make starting together easier without resetting the shared world.

## What Changes

- Disable player-versus-player damage (`PVP=false`) while preserving whitelist-only, LAN-only admission and disabled RCON.
- Give each **new character** a duffel bag, one canned food item, a can opener, a water bottle, and a hatchet using verified installed Build 42 item identifiers; do not enable the game's separate default starter kit or re-grant supplies on reconnect.
- Enable the in-game minimap and show all other players on the in-game map to **authenticated server players** (`MapRemotePlayerVisibility=4`); do not publish positions to unauthenticated users or add telemetry.
- Switch Knox-virus transmission to **saliva only** (`ZombieLore.Transmission=2`) and the global skill XP multiplier to **1.5** (`MultiplierConfig.Global=1.5`, retaining `GlobalToggle=true`).
- Reconcile only these settings through the existing stopped-service NixOS initialization, then perform one requested managed full-state reset before deployment. Preserve only the existing whitelist entries for `Scetrov` and `FlyingFire`; do not restore saves, characters, credentials, mods, or unrelated configuration from the replaced profile.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `project-zomboid-server-runtime`: Declare and validate the requested new-character kit, minimap, transmission, and XP rules in the persistent Build 42 profile.
- `project-zomboid-server-access`: Disable PvP and allow approved players to see teammates on the in-game map without weakening admission or network restrictions.

## Impact

- `src/roles/nixos/files/etc/nixos/modules/project-zomboid.nix`, its existing profile reconciliation, and focused Nix/behavior tests; possibly a small repository-managed server-side script **only if** the built-in `SpawnItems` option cannot reliably provide the specified water and kit on Build 42.
- Habiki's existing `pz-server.ini`, `pz-server_SandboxVars.lua`, and the server's SQLite whitelist data; no new ports, secrets, third-party dependencies, clients, or OpenTofu resources.
- A targeted Habiki NixOS deploy may restart the server; arrange a maintenance window or verify no players are online first. The requested reset replaces saved-world and character state; only the `Scetrov` and `FlyingFire` whitelist records are restored. Existing characters are not retroactively equipped.
