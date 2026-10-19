## Context

Issue #29 reports `GATEWAY METADATA STALE` and no visible scheduled jobs; neither the root cause nor the presence of configured jobs has been established. The repository already runs `hermes-agent` with `gateway run` and shares the Hermes home volume with the WebUI at different container paths. Habiki explicitly uses rootful Podman, disables the separate dashboard, and exposes the WebUI through the existing Authentik/Caddy ingress. Generic rootless health options include a trivial `true` probe, which is not evidence of scheduler health and is not the active Habiki configuration.

Relevant code is `modules/hermes.nix` under `src/roles/nixos/files/etc/nixos/`, the Habiki device configuration, existing `scripts/tests/*hermes*` checks, and `docs/hermes.md`. Existing runtime-access and session-expiry specs remain in force.

## Goals / Non-Goals

**Goals:** Restore fresh gateway metadata and native job execution with minimal changes; prove creation, visibility, execution, and persistence; retain actionable diagnostics and existing access controls.

**Non-Goals:** Another scheduler/container, host cron workaround, rootless migration, separate dashboard enablement, broad dependency refresh, a new health/metrics framework, new ingress routes, or unrelated refactoring.

## Decisions

### 1. Diagnose the existing path before choosing a fix

During apply, identify actual deployed image IDs/digests and relevant upstream behavior, inspect gateway lifecycle and journal/Loki errors, and trace metadata/job storage between the agent and WebUI. Check effective paths, permissions, timestamps/clocks, connectivity, and the scheduler tick only as evidence directs. Read source from the deployed images where necessary rather than assuming the configured tag identifies its contents.

Attempt a disposable local container reproduction using the relevant images and synthetic state before deploying a candidate fix. Reuse existing runtime-test patterns; do not create a general-purpose fixture framework. If the failure depends on Habiki or an inaccessible image, record that limitation and use narrowly scoped live diagnostics instead. A missing local reproduction alone is not a reason to stop all investigation. Do not claim a root cause without evidence.

Alternative rejected: adding a gateway or changing volume layout speculatively. The gateway is already declared, and different mount paths are not themselves proof of a defect.

### 2. Apply the smallest supported correction

Prefer an existing configuration/environment/command, permissions, or state-path correction. Add readiness/restart handling only if lifecycle evidence requires it. Change a specific image only if incompatibility is demonstrated, checking applicable released versions, digest provenance and repository update policy. Preserve persistent volumes, runtime-managed secrets, current rootful operation, Authentik behavior, and private listeners. If an upstream code defect cannot be corrected through supported configuration or an appropriate released image, report the blocker before introducing a maintained fork or broad source patch.

Scheduling fixtures and live test jobs must be created through a repeatable automated native-interface check, not an undocumented UI-only or direct state-file edit. Use a harmless local marker/no external delivery, bound execution and any model cost, and remove only test-owned jobs/markers after verification. Existing jobs are never deleted or rewritten for testing.

### 3. Keep validation and observability proportionate

Add one focused regression check for the demonstrated failure using the existing test structure. Local checks alone are insufficient: record a fresh heartbeat and native job visibility/execution on Habiki, then verify the same job survives and executes after restart and targeted rebuild. Exercise failure visibility safely in the disposable reproduction where possible, using existing native health/status and journal-to-Loki logging. If evidence exposes missing diagnostic logging or health reporting, make only the local correction needed; no new dashboard or alerting stack is required.

### 4. Continue autonomously within the approved scope

During apply, run necessary diagnostics, focused tests, and targeted Habiki deployments without seeking confirmation at every routine step. Stop only for unavailable access/credentials, destructive or out-of-scope action, unacceptable production impact, or an upstream defect requiring a materially different solution. Do not expose secrets in logs or artifacts. This proposal does not itself deploy or implement anything.

## Risks / Trade-offs

- Unknown root cause → Keep the exact patch conditional on reproduction; document before/after evidence.
- A running container can mask a dead scheduler → Verify heartbeat freshness and an actual scheduled execution, not just container state or HTTP liveness.
- Restart/rebuild can interrupt active chats or jobs → Inspect current activity and choose a safe window; block if impact cannot be bounded.
- Private/mutable agent image or mismatched embedded source → Record actual identities and inspect deployed behavior; do not replace images blindly.
- Live fixtures can alter production state or spend inference credit → Use one identifiable, bounded, repeatably provisioned native job; preserve existing schedules and clean up only fixtures.

## Migration Plan

1. Record baseline symptoms and deployed configuration; preserve existing state. Add the minimal fix and focused regression check, then rerun reproduction and relevant existing checks.
2. Deploy through `./scripts/play.sh --limit habiki --tags hermes-runtime`, after checking the current playbook's scope. It rebuilds host configuration and can restart services; the host limit is not a guarantee of zero impact on other services. Use broader Hermes orchestration only if the demonstrated fix needs it; do not change identity resources unnecessarily.
3. Verify metadata refresh over multiple expected heartbeat intervals, native job execution, and persistence/execution after a controlled service restart and targeted rebuild. Preserve Authentik-gated browser access and GitHub CLI behavior. Record redacted evidence and cleanup.
4. If acceptance regresses, redeploy the previous known-good configuration through the same automation without deleting or rolling back persistent job data blindly. No data migration is planned; stop and reassess if one becomes necessary.

## Implementation Evidence: Host Publication Repair

Authenticated-browser acceptance exposed a separate 502 despite healthy
container-local WebUI APIs. Caddy and host-loopback curl reproduced the fault:
an orphaned Hermes Netavark DNAT destination (`10.89.1.9:8787`) preceded the
current container destination. Its dispatch comment referenced a container
confirmed absent. Targeted supported Podman network reload did not remove it.
A disposable network-namespace reproduction went from unreachable to HTTP 200
when only the obsolete DNAT was removed.

Extend the existing focused runtime play with a bounded, idempotent migration
removing only that exact obsolete DNAT and retired-container dispatch rule.
Guard against the retired container still existing or the current container
using the old address; never flush a chain/table or touch other publications.
Check host `http://127.0.0.1:8787/` readiness after restart, not merely service
liveness/container-local API health. This preserves existing topology and
ports; no new routing architecture or generic firewall reconciler is added.

## Open Questions

Resolve during implementation without operator questions unless genuinely blocked: which image behavior produces the warning; where the WebUI reads the heartbeat and job inventory; whether the scheduler is ticking; and whether the inventory is legitimately empty. These are diagnostic questions, not grounds to preselect a new architecture.
