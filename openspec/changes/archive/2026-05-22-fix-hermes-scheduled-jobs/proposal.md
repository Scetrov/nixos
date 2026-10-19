## Why

Issue #29 reports stale gateway metadata and apparently nonfunctional Hermes scheduled jobs on Habiki. Restore the native scheduling path with the smallest evidence-backed change, rather than adding another scheduler or redesigning the deployment.

## What Changes

- Establish whether the deployed gateway is running, refreshing the metadata consumed by the WebUI, and ticking its scheduler; distinguish an empty schedule from a failure.
- Correct only the demonstrated runtime/configuration, shared-state, permissions, or image-compatibility defect using existing NixOS/Ansible automation.
- Verify a harmless native scheduled job is visible and executes, including after service restart and a targeted Habiki rebuild.
- Add a focused regression check and concise operational evidence/recovery notes; reuse existing journal/Loki logging and native health signals.
- During implementation, proceed autonomously with targeted Habiki deployments when required; escalate only genuine access, safety, or upstream blockers.

## Capabilities

### New Capabilities

- `hermes-native-scheduling`: A live native gateway, fresh scheduling metadata, and persistent, executable jobs on Habiki.

### Modified Capabilities

None. Existing Authentik access, session-expiry, and GitHub CLI requirements remain unchanged.

## Impact

- Primary candidate: `src/roles/nixos/files/etc/nixos/modules/hermes.nix`; Habiki overrides in `src/roles/nixos/files/device-configuration/habiki.nix` only if the diagnosis requires them.
- Focused checks under `scripts/tests/` and operational notes in `docs/hermes.md`.
- `src/hermes-runtime.yml`: exact guarded cleanup of demonstrated orphaned Hermes hostport rules and host-loopback readiness verification after authenticated acceptance exposed a 502.
- Deployment uses the existing `./scripts/play.sh --limit habiki --tags hermes-runtime` path where sufficient. No new dependencies, ports, public endpoints, or identity changes are planned.
- Preserve existing persistent state and runtime secret management. No broad image refresh, rootless conversion, separate dashboard enablement, external cron workaround, generic monitoring framework, or unrelated cleanup.

Issue: https://github.com/Scetrov/nixos/issues/29
