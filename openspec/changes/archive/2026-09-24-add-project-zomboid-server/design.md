## Context

Habiki is an always-on NixOS infrastructure host with existing NixOS modules, agenix-based runtime secret injection, systemd-managed services, and a default-deny firewall. It has local addresses in the `10.229.0.0/16` network. The requested Project Zomboid Build 42 server is initially for local-LAN players, with possible future access by invited Headscale peers. It must not depend on an interactive terminal, a mutable container tag, or a network-exposed remote administration protocol.

Project Zomboid distributes its dedicated server and Workshop content through Steam rather than a reproducibly versioned upstream artifact. Its mutable configuration, world, player database, logs, downloaded server files, and Workshop cache must therefore live outside the Nix store. A clean in-game `save` followed by `quit` is required before copying world state or performing a planned restart.

The existing Garage service is on Habiki and is intentionally not an off-host disaster-recovery mechanism. The requested backup objective is recovery from accidental world damage, not survival of host or disk loss.

## Goals / Non-Goals

**Goals:**

- Run one persistent Build 42 dedicated server on Habiki as a dedicated unprivileged system user.
- Make service lifecycle, resource limits, LAN ingress, initial server settings, intended Workshop mod manifest, update policy, backup retention, and secrets declarative in NixOS/agenix configuration.
- Use a local private control channel to safely save and stop the server for systemd shutdown, planned restart, backup, and controlled update workflows.
- Provide LAN-only gameplay initially and a separately explicit, disabled-by-default Headscale access path for future invitations.
- Maintain rotating local recovery points and document a tested restore procedure.
- Validate NixOS configuration evaluation and require deployment-time smoke tests for game startup, LAN joining, and Skill Recovery Journal loading.

**Non-Goals:**

- Public internet publishing, router port forwarding, public server-list registration, or public RCON.
- Off-host backup, high availability, replication, or recovery from Habiki/SSD loss.
- Automatic game or Workshop updates during ordinary service starts.
- Supporting multiple concurrent Project Zomboid instances.
- Migrating an existing Build 41 world or guaranteeing compatibility across Build 42 game/mod releases.
- Providing a general game-server hosting platform.

## Decisions

### Use a native systemd service with the Nixpkgs SteamCMD wrapper

The new module SHALL provision a dedicated system user and persistent state beneath `/var/lib/project-zomboid`. A systemd service SHALL run the official Steam app `380870` through the Nixpkgs SteamCMD/Steam runtime support, with the server's mutable runtime and all game-owned data outside `/nix/store`.

**Rationale:** This fits the repository's NixOS-native service model, avoids an unpinned third-party container image, and keeps host lifecycle controls visible in the Nix configuration. Steam content cannot be fully content-addressed by Nix because Valve distributes it as a mutable service; the controlled update process is the compensating boundary.

**Alternatives considered:** A third-party container wrapper would reduce initial scripting but adds another supply-chain dependency and commonly relies on mutable image tags. A prebuilt Nix derivation cannot reliably package changing Steam server/Workshop artifacts or permit the game to write its required state.

### Separate immutable desired configuration from game-owned persistent state

The module SHALL keep a reviewed desired configuration template and mod manifest in the repository, then initialize or reconcile the active server profile only while the server is stopped. Game-owned paths—including saves, database, logs, generated configuration, Steam app files, and Workshop cache—SHALL remain persistent under the service state directory.

The initial profile SHALL select Build 42 and include Skill Recovery Journal only after the deployment workflow verifies its current Workshop item ID, internal mod ID, Build 42 compatibility, and any declared dependencies from downloaded metadata. Administrative credentials and any join/RCON credentials SHALL be injected from agenix; no plaintext credential SHALL enter Nix expressions or OpenSpec files.

**Rationale:** Read-only Nix-store configuration conflicts with Project Zomboid's normal writes. Keeping a declarative desired source while preserving game-owned state permits rebuilds without overwriting a live world and makes configuration drift visible.

**Alternatives considered:** Managing the live configuration solely by hand makes the service non-reproducible. Mounting the live configuration read-only from the Nix store risks failed starts or overwritten settings.

### Use a FIFO-based graceful lifecycle, with crash and planned restart treated differently

The service SHALL receive a private control FIFO owned by the service identity. Its stop path SHALL send `save`, wait for the world flush, then send `quit`, and systemd SHALL allow a bounded graceful-stop period before failure handling. Unexpected failures SHALL use `Restart=on-failure`, a restart delay, and start-rate limiting. A scheduled planned restart SHALL use the same graceful pathway rather than terminating the JVM directly.

**Rationale:** A crash restart restores availability, while a planned operation must preserve world consistency. Keeping the command path local removes the need to expose RCON.

**Alternatives considered:** Killing the process can corrupt or lose recent world state. RCON provides remote control but unnecessarily expands the network and credential attack surface.

### Restrict network exposure to named trusted paths

Gameplay traffic SHALL be permitted only from configured LAN source CIDRs and only on the minimal UDP ports/range empirically verified for the selected Build 42 server profile. No remote administration port SHALL be exposed. Headscale access SHALL be represented as a separately configurable, disabled-by-default firewall path; enabling it later requires explicitly naming the relevant interface/address policy and testing a peer join.

The server SHALL not be publicly listed, and initial account admission SHALL use a non-public policy such as a join password and/or whitelist.

**Rationale:** LAN access satisfies the immediate need without a WAN listener. Separating future Headscale access prevents a broad rule from being introduced prematurely.

**Alternatives considered:** Opening historical broad Project Zomboid port ranges globally is incompatible with least privilege. WAN publishing and router forwarding are out of scope.

### Make updates manual maintenance operations with a pre-update backup and smoke test

Ordinary service starts SHALL not update the Steam app or Workshop content. A separate manually invoked maintenance operation SHALL take the service lock, gracefully stop the server, create a local recovery point, run SteamCMD update/validation, restart the service, inspect startup logs, and require an administrator LAN join smoke test before the change is accepted.

Workshop changes SHALL follow the same flow. The mod manifest SHALL be added in small reviewable increments, with dependencies ordered before dependent mods.

**Rationale:** Build and Workshop updates can create player-version mismatches or mod/world regressions. A controlled window gives operators a rollback point and a bounded verification step.

**Alternatives considered:** Updating on each boot makes restarts nondeterministic and can break a previously working world without a known pre-update recovery point.

### Use rotating local full-state backups for accidental-damage recovery

A systemd timer SHALL invoke a serialized backup operation that gracefully stops the server, creates a timestamped compressed archive of the complete mutable game state, applies bounded retention, and restarts the service. The same backup function SHALL be used before maintenance updates and risky configuration/mod migrations. An operator runbook SHALL describe restore into a stopped service, retention expectations, and a periodic restore validation.

**Rationale:** Full-state archives protect maps, player data, server settings, and mod configuration together. Local backups meet the stated accidental-damage objective without implying disaster recovery.

**Alternatives considered:** Copying while the server runs risks inconsistency. Backing up only the map omits player/configuration state. Garage or another local same-host target adds complexity without meeting an off-host durability goal.

## Validated deployment inputs

The following values were verified in a disposable x86_64 NixOS test state on 2026-09-21:

- Nixpkgs provides `steamcmd` and `steam-run`; the server launcher requires an explicit Nix Bash invocation (`bash ./start-server.sh`) because its upstream shebang is `/bin/bash`.
- Steam app `380870` default branch installed Build 42 dedicated-server build `24909836`. The verified launch argument is `-servername <name>`; the generated profile is `$HOME/Zomboid/Server/<name>.ini`.
- The server configured `DefaultPort=16261` and `UDPPort=16262` and listened on both UDP ports. Steam additionally opened UDP `60719` during the test; it must be attributed and revalidated before it is added to a static firewall policy.
- Skill Recovery Journal's declared Workshop manifest is dependency-first: `3077900375` / `ChuckleberryFinnAlertSystem`, `2896041179` / `errorMagnifier`, then `2503622437` / `SkillRecoveryJournal`. The Build 42 `mod.info` files use backslash-prefixed dependency identifiers.
- Workshop downloads require a Project Zomboid-licensed dedicated Steam account. Its session belongs in the service-owned mutable Steam state and is used only by controlled maintenance operations.

Initial operating policy is: allow `10.229.0.0/16`; use both an encrypted join password and an explicit whitelist; cap the server at 8 players and the JVM at 4 GiB; make a daily 04:00 local-time backup; and perform a weekly planned restart every Monday at 04:15 local time.

## Risks / Trade-offs

- [Steam and Workshop artifacts are mutable and not hash-pinned] → restrict retrieval to manually approved maintenance windows, validate server files, record installed build/mod metadata in logs or the runbook, take a pre-update archive, and smoke-test before reopening access.
- [A Build 42 game update or Skill Recovery Journal update breaks compatibility] → do not auto-update; preserve a pre-update backup and update only after checking current build/mod compatibility.
- [LAN game ports are too broad or incorrect] → derive the rule from generated server configuration and a LAN join test; document the tested port policy and do not expose RCON.
- [A bad shutdown or overlapping automation corrupts the world] → use one lock shared by service maintenance, restart, and backup operations; require FIFO `save`/`quit`; use bounded timeouts and surface failures in systemd logs.
- [Local archives exhaust Habiki storage] → configure bounded retention, reserve capacity, measure archive growth after play, and expose backup failures through service/timer status and existing log collection.
- [The same-host backups cannot survive host loss] → document that they are recovery points only and do not label them disaster recovery.
- [Resource contention with existing Habiki workloads affects infrastructure services] → declare JVM memory ceiling and systemd resource limits, start with a conservative player limit, and revise after live load observation.

## Migration Plan

1. Add and evaluate the new module without enabling it on Habiki; confirm package availability and systemd/firewall rendering.
2. Provision encrypted administrative and admission credentials through the existing agenix/Ansible secret workflow.
3. Enable the module through the targeted Habiki NixOS deployment path; perform the first Steam download and server-profile initialization in a controlled maintenance window.
4. Verify the generated Build 42 profile, minimal UDP rule, non-public admission policy, and absence of a network-exposed administration port.
5. Add and verify Skill Recovery Journal against its installed metadata and logs; perform an administrator LAN join test and in-game functionality check.
6. Exercise graceful restart, backup, and local restore in a non-production/test world or from a known recovery point.
7. Record installed version, mod manifest, baseline storage consumption, and the tested port policy in the operator runbook.

**Rollback:** Gracefully stop and disable the service and timers, remove its firewall rules, and retain `/var/lib/project-zomboid` unchanged until an explicit data-retention decision. Restore the prior NixOS generation if the module causes host configuration problems. Do not delete a world or backup archive as part of rollback.

## Open Questions

- Which precise LAN source CIDR(s) should be permitted: the complete `10.229.0.0/16` network or selected VLANs only?
- What initial player limit and JVM memory ceiling leave sufficient capacity for existing Habiki infrastructure workloads?
- What backup/restart schedule fits the group’s play hours and acceptable downtime?
- Should initial admission use a shared join password, explicit whitelist accounts, or both?
- Which Build 42 release/Steam branch is current at deployment time, and which exact Skill Recovery Journal dependencies and load-ID syntax does that release require?
