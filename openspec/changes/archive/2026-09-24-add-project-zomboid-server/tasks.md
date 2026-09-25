## 1. Validate deployment inputs

- [x] 1.1 Inspect the pinned NixOS/nixpkgs inputs to verify that SteamCMD and its required Steam runtime support are available for Habiki's architecture.
- [x] 1.2 In a disposable local test state, obtain Steam app `380870` through SteamCMD and verify the current Build 42 server branch, launch arguments, generated profile locations, and actual game UDP port policy.
- [x] 1.3 Verify the current Skill Recovery Journal Build 42 Workshop item, internal mod ID, dependencies, load-order requirements, and installed metadata syntax; record the verified values in the declarative mod manifest and runbook.
- [x] 1.4 Decide and document initial LAN source CIDRs, player limit, JVM memory/resource limits, admission policy, and planned backup/restart schedule.

## 2. Implement the NixOS runtime module

- [x] 2.1 Add a `project-zomboid.nix` module that provisions the dedicated non-root service identity and persistent service-owned state directories under `/var/lib/project-zomboid`.
- [x] 2.2 Add declarative options and a stopped-service initialization/reconciliation path for the Build 42 server profile, mutable data paths, mod manifest, resource limits, and secret-file inputs without overwriting an existing world.
- [x] 2.3 Add agenix secret declarations and deployment-secret workflow entries for the administrator and selected admission credentials; verify no plaintext credentials appear in tracked files.
- [x] 2.4 Add the dedicated-server systemd unit using the verified SteamCMD/Steam runtime invocation, persistent paths, bounded resource settings, and `Restart=on-failure` rate-limited recovery.
- [x] 2.5 Implement the private service-owned FIFO control channel and the bounded `save` then `quit` stop/restart sequence.
- [x] 2.6 Import and enable the module in Habiki's device configuration with the selected initial server settings and verified Skill Recovery Journal manifest.

## 3. Restrict gameplay access

- [x] 3.1 Add source-restricted firewall rules for only the validated LAN CIDRs and minimum verified Project Zomboid UDP ports/range.
- [x] 3.2 Configure non-public server listing and the selected password and/or whitelist admission policy.
- [x] 3.3 Ensure RCON and other remote-administration listeners are disabled and absent from firewall exposure.
- [x] 3.4 Add a disabled-by-default Headscale gameplay-access option that requires explicit source/interface configuration and does not widen LAN access.

## 4. Implement controlled maintenance and local recovery

- [x] 4.1 Implement a shared-lock maintenance helper for planned restart, backup, restore, profile migration, and update operations.
- [x] 4.2 Implement a timer-driven backup operation that gracefully stops the server, creates timestamped compressed full-state archives, applies bounded retention, and restarts the server.
- [x] 4.3 Implement a manually invoked controlled-update operation that creates a pre-update recovery point, runs SteamCMD update/validation, verifies configured Workshop metadata, starts the service, and preserves recovery state on failure.
- [x] 4.4 Ensure normal service starts never run Steam or Workshop updates.
- [x] 4.5 Write a Project Zomboid operator runbook covering controlled update, planned restart, log inspection, local restore with live-state quarantine, retention, and the same-host backup limitation.

## 5. Validate and deploy

- [x] 5.1 Add a NixOS evaluation test covering module enablement, unprivileged service configuration, persistent paths, graceful lifecycle settings, secret references, firewall scope, disabled-by-default Headscale access, and maintenance timers.
- [x] 5.2 Run formatting and the relevant NixOS evaluation tests; resolve all failures before deployment.
- [x] 5.3 Deploy through the targeted Habiki NixOS automation path and confirm initial Steam download/profile initialization succeeds.
- [x] 5.4 Perform and document LAN gameplay smoke tests, including connection from an approved source, rejection from an unapproved source, non-public admission enforcement, absence of exposed RCON, and Skill Recovery Journal loading/functionality.
- [x] 5.5 Exercise and document graceful planned restart, crash restart behavior, scheduled backup creation/retention, controlled-update rollback behavior, and a local full-state restore validation. (The failed-update path is covered by a sandboxed maintenance test; live maintenance validation, including restore, is recorded in the operator runbook.)
