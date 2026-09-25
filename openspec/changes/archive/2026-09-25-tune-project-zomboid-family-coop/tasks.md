## 1. Confirm the installed Build 42 contract

- [x] 1.1 Verify Habiki's installed `pz-server.ini` definitions for `PVP`, `MapRemotePlayerVisibility`, and `SpawnItems`; inspect the server-side `SpawnItems.OnNewGame` implementation and all five item IDs against the installed Build 42 content.
- [x] 1.2 Verify the sandbox table paths for `Map.AllowMiniMap`, `ZombieLore.Transmission`, and `MultiplierConfig.Global/GlobalToggle`; capture current settings, the existing world/profile, and the whitelist database schema without printing credentials.
- [x] 1.3 Determine in a controlled new-character test whether `Base.WaterBottle` spawned via `SpawnItems` contains drinkable water; if not, identify and verify the smallest supported server-side fill mechanism before implementing it.

## 2. Declare the family co-op profile

- [x] 2.1 Add allowlisted NixOS options and stopped-service INI reconciliation for `PVP=false`, `MapRemotePlayerVisibility=4`, and one `SpawnItems` list with duffel bag, canned chili, can opener, water bottle, and hatchet; retain `StarterKit=false` and all existing access controls and secrets.
- [x] 2.2 Reconcile `Map.AllowMiniMap=true`, `ZombieLore.Transmission=2`, and `MultiplierConfig.Global=1.5` with `GlobalToggle=true` using safe nested-table matching; leave unrelated sandbox and saved-world state untouched and fail on ambiguous structure.
- [x] 2.3 If the controlled bottle check fails, add a minimal server-side once-per-new-character water-fill hook using the verified Build 42 API, without client software, duplicate items, or a third-party mod.
- [x] 2.4 Extend the managed reset to preserve exactly the existing `Scetrov` and `FlyingFire` whitelist records through a full profile reset, using restrictive temporary storage and failure on missing or duplicated records; do not retain any other player, whitelist, world, or credential state.
- [x] 2.5 Update the Project Zomboid operations documentation with the co-op rules, map-sharing privacy implications, exact starter kit, requested full-reset behavior, retained whitelist entries, and the fact that existing characters are not retroactively equipped.

## 3. Prove behavior without damaging the world

- [x] 3.1 Add Nix evaluation and offline fixture tests for first-run and existing-profile reconciliation, nested-key scoping, repeat-run idempotence, malformed-profile failure, safe INI permissions, and no changes to secrets, mods, or unrelated settings; add reset fixtures that preserve only the two named whitelist records while replacing world and character data.
- [x] 3.2 Add tests that validate the five item IDs against the installed Build 42 metadata, keep the separate default StarterKit off, and detect a missing, duplicated, or non-potable starter item; test missing or duplicate requested whitelist records fail before reset.
- [x] 3.3 Run Nix evaluation, focused script tests, Ansible syntax checks, and OpenSpec validation before deployment.

## 4. Deploy and verify safely

- [x] 4.1 Check the live player count, arrange a maintenance window as needed, and create a managed full-state backup before the targeted Habiki `nixos` deployment and requested reset.
- [x] 4.2 Deploy through `./scripts/play.sh --limit habiki --tags nixos --skip-generated-refresh`, perform the requested managed full reset, and verify running service health, exact INI/sandbox values, private admission, RCON disabled, exact retained whitelist names, and replacement of the old saved world without printing credentials.
- [x] 4.3 With approved players, verify a new character receives the specified five items including drinkable water; verify no duplicate grant on reconnect, a kit for a replacement character, visible teammate map markers, and PvP disabled. Record any test blocked by unavailable players instead of claiming success.
