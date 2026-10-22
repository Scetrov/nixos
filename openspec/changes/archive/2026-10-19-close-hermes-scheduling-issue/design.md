## Context

Issue #29 reports stale gateway metadata and apparently missing scheduled jobs. The archived `2026-05-22-fix-hermes-scheduled-jobs` change is complete; `docs/hermes.md` records an empty original inventory, a demonstrated heartbeat fault, a compatible image/source-volume correction, native fixture execution across restart/rebuild, and operator-confirmed UI acceptance. Archive directory dating is not proof of chronology; use recorded deployment/acceptance evidence. These are historical records, not a new live observation.

## Goals / Non-Goals

**Goals:** Establish that each issue acceptance criterion has applicable evidence and close the stale issue with a useful audit trail.

**Non-Goals:** Runtime fixes, another rebuild, destructive job fixtures, image upgrades, or changing the existing native scheduling specification.

## Decisions

1. **Reuse existing lifecycle acceptance.** Map each issue criterion to the archived tasks and runbook before collecting anything new. Repeating restarts/rebuilds solely for issue bookkeeping adds production risk without value.
2. **Add bounded freshness confirmation.** Compare current managed image/source-volume configuration with recorded acceptance and use existing read-only health/job status and journal/Loki signals over multiple heartbeat intervals. Use approved operator/browser access when authentication is needed; do not bypass Authentik. If live access is unavailable, document the limitation and leave closure pending unless equivalent current evidence is supplied.
3. **Gate the GitHub mutation.** During implementation, post a redacted `gh` closure comment linking repository evidence and current verification, then close #29 as completed only if no criterion remains unmet. Historical fixture results can satisfy lifecycle criteria when the relevant deployed configuration is unchanged. A demonstrated regression stays open for separately scoped remediation.
4. **No generic issue-closing framework.** This is a bounded operational/documentation task, not a new automation service.

## Risks / Trade-offs

- [Recorded acceptance no longer matches production] → Compare relevant configuration and current health; do not infer health from archive completion.
- [Verification requires privileged access] → Prefer existing probes and operator confirmation; no credential dumping, direct backend exposure, or bypass.
- [Overstating browser evidence] → Distinguish operator confirmation from automated browser checks.

## Migration Plan

No runtime migration or deployment. Review evidence, collect bounded read-only confirmation, update documentation only if necessary, publish the evidence summary, and close the issue. If the closure is later shown incorrect, reopen #29 with the contradictory evidence; preserve the audit trail.

## Open Questions

- Does current Habiki configuration match the accepted scheduling repair?
- Is approved current health/browser evidence available during implementation?
