# Project Zomboid operations

## Scope and access

This is one Build 42 dedicated server on Habiki. Gameplay is LAN-only from
`10.229.0.0/16` on UDP `16261` and `16262`. It is not publicly listed; it
requires both the agenix-backed join password and explicit whitelist approval.
RCON is disabled and must never be exposed.

The managed Build 42 sandbox grants 100 free character-creation points and
sets `MultiHitZombies = true`. These keys are reconciled on service start while
the server is stopped; existing saves, profiles, and unrelated sandbox options
remain game-owned. A targeted NixOS rebuild can restart the game, so deploy
when players are offline or during a maintenance window.

The verified dependency-first Workshop manifest is:

1. `3077900375` / `ChuckleberryFinnAlertSystem`
2. `2896041179` / `errorMagnifier`
3. `2503622437` / `SkillRecoveryJournal`

Build 42 metadata requires the backslash-prefixed mod-ID syntax. Do not change
mod IDs or their order without downloading and inspecting each item's installed
`mod.info` first.

## Routine operations

Inspect status and logs:

```sh
systemctl status project-zomboid
journalctl -u project-zomboid -b
```

For a planned restart or backup, use the serialized helper:

```sh
sudo project-zomboid-maintenance restart
sudo project-zomboid-maintenance backup
```

The scheduled backup runs daily at 04:00 local time. Planned restart is Monday
at 04:15 local time. Backups are compressed full-state archives under
`/var/lib/project-zomboid/backups`; retain seven archives unless the declarative
retention setting is changed.

## Controlled update

Normal starts never download Steam or Workshop content. During a maintenance
window, first ensure the service account has an active licensed Steam session,
then run:

```sh
sudo project-zomboid-maintenance update
```

The helper takes the shared lock, stops gracefully, creates a pre-update archive
(including the Steam account/session), validates app `380870`, downloads every
declared Workshop item as the dedicated service user, and starts the service.
Inspect logs and perform a LAN join plus Skill Recovery Journal smoke test before
accepting the update. If SteamCMD or verification fails, the service stays
stopped; **do not start the partially updated server**. Restore the printed
pre-update recovery point first. If the join/smoke test fails after startup,
stop the service and restore that recovery point.

On a fresh world the administrator password is supplied once through the
service-owned console FIFO and retained in the account database, not passed as
a process argument. Rotating the agenix password alone does not change the
existing in-game administrator password; rotate the account in-game as well.

## Restore validation

1. Run `sudo project-zomboid-maintenance restore /var/lib/project-zomboid/backups/ARCHIVE.tar.gz`.
   The helper validates and stages the archive before stopping the service;
   corrupt archives leave the live state untouched.
2. The helper takes the lock, stops gracefully, quarantines the previous live
   `steam`, `Zomboid`, and (where archived) `.local` and `.steam` paths, installs
   the staged files with service ownership, and starts the service.
3. Inspect service logs, verify the saved world loads, and join from the LAN.
   Older archives may not contain the Steam account/session; reauthenticate
   before the next controlled update if restoring one of those archives.

These archives protect against accidental world damage only. They are on Habiki
itself and do **not** provide recovery from loss of Habiki or its storage.

## Fresh-world reset

To archive the complete current state and start a fresh world **including a new
account database**, run the explicitly confirmed operation:

```sh
sudo project-zomboid-maintenance reset-world --confirm
```

It retains the installed Steam runtime and Workshop cache, quarantines the old
`Zomboid` state beneath `/var/lib/project-zomboid`, and regenerates the server
profile. Players must be re-added to the whitelist afterwards. Do not use this
operation for a map-only reset.

## Validation record

On 2026-09-23, an approved LAN player successfully joined the server and an
external connection attempt was rejected. The server listens only on UDP 16261
and 16262; RCON is disabled. Startup logs confirm the configured Workshop
items, including `SkillRecoveryJournal`, load successfully. Scetrov completed the
in-game Skill Recovery Journal recipe smoke test successfully. Repeat that
smoke test after future mod updates.

On 2026-09-24, maintenance validation exercised the timer-backed backup unit
and its seven-archive retention, a graceful planned restart, and a forced
process termination. Systemd restarted the failed service (restart counter
increased from 0 to 1). The failed Steam-update path is covered by the
sandboxed maintenance test, which verifies that a failed update preserves its
recovery point and leaves the service stopped.

A live restore validation then created and restored
`20260924T175109Z-backup.tar.gz` using the maintenance helper. The helper
quarantined the prior live state at
`/var/lib/project-zomboid/quarantine-20260924T175745Z`, restored the full-state
archive with `project-zomboid:project-zomboid` ownership, and restarted the
private profile. The service became active and UDP listeners returned on ports
16261 and 16262. This validates the local recovery and restore path.
