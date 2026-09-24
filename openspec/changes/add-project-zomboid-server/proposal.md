## Why

Habiki needs a reliable local-LAN Project Zomboid Build 42 server for a small group without relying on an interactive shell or unmanaged host state. The server must preserve its world across rebuilds, recover safely from failures, and make updates and Workshop mod changes deliberate rather than accidental.

## What Changes

- Add a NixOS-native Project Zomboid dedicated-server module and enable it on Habiki.
- Run the Steam-distributed dedicated-server runtime under a dedicated unprivileged service identity with persistent game, configuration, Workshop, log, and world state.
- Configure a Build 42 world with the Skill Recovery Journal Workshop mod and make the desired mod manifest declarative and reviewable.
- Expose only the minimally required game UDP traffic to approved local-LAN networks; keep remote administration private and establish an explicit path for future Headscale access.
- Add graceful crash recovery, planned restart, controlled update, and local rotating-backup operations that protect against accidental world damage.
- Add configuration evaluation and operational validation coverage for the new Habiki service.

## Capabilities

### New Capabilities
- `project-zomboid-server-runtime`: A persistent, NixOS-managed Build 42 dedicated-server runtime on Habiki with a declarative server/mod configuration and safe service lifecycle.
- `project-zomboid-server-access`: Restricted LAN game access with a separately controlled future Headscale-access path and no exposed remote administration endpoint.
- `project-zomboid-server-maintenance`: Controlled game and Workshop updates, graceful planned restarts, and local rotating backups/restoration procedures for accidental-world-damage recovery.

### Modified Capabilities

None.

## Impact

- Adds a Habiki import and a new NixOS module beneath `src/roles/nixos/files/etc/nixos/modules/`.
- Adds a dedicated system user, persistent `/var/lib` state, systemd services/timers, firewall rules, and encrypted runtime secret handling for administrative credentials.
- Uses the Nixpkgs SteamCMD/Steam runtime integration to obtain Valve-distributed server content at controlled maintenance time; this mutable upstream runtime is not stored in the Nix store.
- Adds NixOS evaluation tests and an operator runbook; deployment remains through the repository's targeted NixOS/Ansible automation.
