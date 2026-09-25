## Context

Habiki runs one persistent Build 42 dedicated server with a private, whitelist-only LAN admission path and RCON disabled. NixOS creates the INI on first boot and reconciles a small allowlist of sandbox values at service start, without deleting saved worlds or regenerating the profile. The installed profile currently has `PVP=true`, `MapRemotePlayerVisibility=1` (hidden), `Map.AllowMiniMap=false`, `ZombieLore.Transmission=1` (blood and saliva), `MultiplierConfig.Global=1.0` with `GlobalToggle=true`, and `StarterKit=false`.

The installed Build 42 `SpawnItems.OnNewGame` handler runs server-side and honors the built-in comma-separated INI `SpawnItems` list for a new multiplayer character. Its separate `StarterKit=true` option gives a **different** kit, so it should stay disabled. Installed item definitions include `Base.Bag_DuffelBag`, `Base.CannedChili`, `Base.TinOpener`, `Base.WaterBottle`, and `Base.HandAxe`. `Base.WaterBottle` has a fluid-container definition that can choose between water and carbonated water; the implementation must verify the spawned bottle is drinkable water and, if needed, use a narrowly scoped supported server-side fill hook rather than assume its initial contents.

## Goals / Non-Goals

**Goals:** Make the server co-operative, give each newly created character the requested supplies once, enable minimap/teammate visibility for approved players, and set saliva-only infection and 1.5× global skill XP. Preserve existing credentials, the `Scetrov` and `FlyingFire` whitelist approvals, mods, and unrelated options through one requested managed reset.

**Non-Goals:** Grant supplies retroactively to existing characters or on each login; retain the replaced world or character saves; disable all zombie infection (`Transmission=4`); reveal player positions publicly or through a new API; install a client mod or enable RCON.

## Decisions

### Reconcile a small allowlist in the existing persistent profile

Add explicit desired values to the existing NixOS Project Zomboid service module and apply them while the game is stopped through `ExecStartPre`. Create these keys on initial profile generation and reconcile existing values idempotently. INI keys: `PVP=false`, `MapRemotePlayerVisibility=4`, and a comma-separated `SpawnItems` list. Preserve `Open=false`, `Public=false`, `RCONPort=0`, the vault-sourced join password, mods, and every unrelated INI key; never rewrite the entire live INI from a template.

Sandbox keys: `Map.AllowMiniMap=true`, `ZombieLore.Transmission=2`, and `MultiplierConfig.Global=1.5` with `GlobalToggle=true`. Use table-aware matching or a similarly bounded implementation for nested Lua tables; the existing top-level `set_sandbox_value` function is **not** sufficient to safely address nested keys. Reject ambiguous or malformed sections instead of silently inserting a key in the wrong table. Keep `StarterKit=false` to prevent an unwanted duplicate kit. Alternatives rejected: imperative console/GUI edits, a full profile rewrite, and changing `MapAllKnown` (which would remove exploration).

### Use Build 42's server-side new-character item grant

Prefer INI `SpawnItems=Base.Bag_DuffelBag,Base.CannedChili,Base.TinOpener,Base.WaterBottle,Base.HandAxe`, with the exact IDs verified against the installed Build 42 item scripts as part of implementation. The installed `SpawnItems.OnNewGame` hook grants the INI list on the server for a newly created multiplayer character, not on every reconnect. Supplies need not be auto-equipped or packed inside the bag; item counts and water contents **must** be validated with a controlled new-character/reconnect test. If the default bottle is not reliably potable water, add only the smallest server-side, once-per-character adjustment using a verified Build 42 fluid API; do not enable the separate built-in starter kit or add client-side dependencies. A different food item can be substituted before implementation if requested; canned chili is the concrete, installed shelf-stable default.

### Preserve only the requested whitelist entries during the reset

The Build 42 server's `whitelist` table is in `${profileDir}/db/${serverName}.db`; its records include password-derived authentication data and must not be printed or committed. Before the managed full-state backup/reset, stop the service and copy only the complete whitelist records whose usernames are exactly `Scetrov` and `FlyingFire` to a `0600` temporary SQLite database. Fail if either username does not resolve to exactly one record. After the clean profile has created its new database, stop the service and restore only those two records through parameterized SQLite operations, verify there are exactly two requested entries, and securely delete the temporary database. Do not restore player saves, roles for other accounts, world data, or secrets. Test this flow only against fixtures before the maintenance-window deployment.

### Keep map visibility private to approved players

The installed INI documents `MapRemotePlayerVisibility` values as 1=Hidden, 2=Friends, 3=Friends and nearby, 4=Everyone. Use `4` for visibility to other connected, whitelisted players as requested. This changes **in-game** map sharing, not the authenticated Grafana dashboard, metric labels, network listeners, or public world listing. `PVP=false` removes accidental friendly damage even when the existing safety system is present.

## Risks / Trade-offs

- [A client or other server account sees player positions] → The intended visibility is all approved players, not only friends. Keep whitelist, password, LAN firewall, and Grafana tile authorization unchanged; call out the privacy trade-off in the runbook.
- [An item ID or fluid default differs in the deployed build] → Check installed item definitions before deploy and perform a controlled first-spawn inventory/water test. Fail the acceptance test rather than claiming the kit is correct.
- [The default kit duplicates supplies or returning players get a new kit] → Keep `StarterKit=false`; test a new character, reconnect, and a respawn separately using the game's built-in OnNewGame path.
- [Broad regex changes unrelated Lua keys or exposes the join password] → Patch only validated top-level INI names and exact nested sandbox-table paths while stopped. Use atomic writes, file permissions, scoped tests and no logging of the INI content.
- [Changing existing infection/XP rules surprises players] → Document that these are server-wide rules effective after restart; reset world and characters only through the explicit managed migration; do not backfill skills or disease state.
- [Whitelist restoration loses or exposes authentication data] → Snapshot and restore only the two exact rows while stopped, with restrictive temporary-file permissions and no logging; fail closed on missing or duplicate rows.
- [Deploy interrupts connected players] → Check live player count and take a managed backup, then perform a targeted Habiki NixOS deployment during a suitable window.

## Migration Plan

1. Validate the installed INI enum comments, item definitions, new-character hook, and nested sandbox structure; implement idempotent reconciliation and tests using fixture copies, not the live profile.
2. Run Nix evaluation, script behavior tests, and Ansible syntax checks. Confirm the join password, RCON, mods, unrelated settings, and only the requested whitelist records are protected.
3. During a maintenance window, back up the persistent state, snapshot the exact `Scetrov` and `FlyingFire` whitelist records, deploy with a targeted Habiki `nixos` run, and perform the managed reset. Verify actual INI/sandbox values and restored whitelist names without printing authentication data; confirm normal service/metrics operation.
4. With consenting approved players, test a new character's five supplies and drinkable water, reconnect without duplicate grants, teammate markers on the minimap/world map, and absence of PvP damage. Confirm XP/infection configured values; do not stage unsafe PvP or infection tests with unsuspecting players.
5. For rollback, revert the declared values and redeploy the same targeted automation; restore the pre-reset backup only if the reset or migration must be rolled back.

## Open Questions

- Does the installed Build 42 `Base.WaterBottle` grant reliably potable water via `SpawnItems`, or does it require a minimal server-side fill hook? Resolve with a controlled first-spawn test before marking the change complete.
