## Context

The private Habiki Forgejo service already has persistent storage, native OIDC, metrics, and journal/Loki integration; Actions remains disabled. Existing `forgejo-reconcile.py` reconciles identity, not repository mirrors, and must not become a generic mixed-purpose reconciler. Issue #26 requests Git content mirrors, not GitHub platform-data migration.

## Goals / Non-Goals

**Goals:** Automatically discover and mirror the three requested owner/pattern sets, preserve private access, converge idempotently, synchronize Git changes, and make failures recoverable.

**Non-Goals:** Actions runners; issues/PRs/release metadata migration; bidirectional synchronization; automatic deletion; rewriting submodule URLs; a shared discovery framework with #27; or claiming mirrors provide complete disaster recovery.

## Decisions

1. **Small standalone reconciler with declarative policy.** Configure owners, case-insensitive owner/name glob matching, patterns, eligibility, cadence, namespaces, and report-only mode in NixOS. The operator approved inclusion of `AniCraft` under `storytold/*craft`. Use GitHub user/organization repository APIs with complete pagination and bounded retries/rate-limit handling. Default eligibility includes public, non-fork, non-archived repositories; private/fork/archived inclusion is explicit and documented. Report exclusions so “all eligible” is auditable.
2. **Report before writing.** Inventory counts, destination collisions, permissions, and storage expectations before initial import. Require explicit adoption approval for the discovered plan through managed configuration/deployment; do not modify unrelated repositories.
3. **Forgejo owns Git synchronization.** A scheduled oneshot discovers sources and creates missing native pull mirrors through supported Forgejo APIs; Forgejo handles subsequent branch/tag polling. Confirm API behavior, private-source credential storage, supported mirror refresh/status, and token scope in the installed release before implementing. Do not embed authenticated clone URLs or credentials in Nix/logs.
4. **Durable identity and ownership.** Track stable GitHub repository IDs and source-owner IDs to managed destinations in service-owned state, plus a recognizable managed marker where supported. Explicitly authorize private destination organizations by stable Forgejo ID with owner-controlled access. Permanent account/organization/membership state is managed in a separate OpenTofu root and PostgreSQL schema. Native migration rejects ordinary write-team membership, so the operator approved organization ownership for the globally non-admin service identity in exactly the three dedicated namespaces; `scetrov` retains human ownership and the service token has only repository-write/organization-read scopes. The operator approved deterministic namespaces `gh-Scetrov`, `gh-RichardSlater`, and `gh-storytold` to avoid user/organization collisions; provisioning and authenticated report-only collision checks completed before explicit conditional import approval. The approved 35 public-only destinations are now imported; final live acceptance remains tracked separately. Preserve existing Forgejo `FORCE_PRIVATE` behavior; never broaden repository visibility. Treat destination collisions and uncertain ownership as actionable conflicts rather than adopting or overwriting repositories.
5. **Conservative lifecycle.** Source rename/transfer/deletion/visibility changes produce status requiring review and never delete destination data or silently retarget mirrors. Existing mapped destinations remain stable until an explicit managed migration. Disabling discovery leaves repositories intact; document whether native polling continues and how to suspend it deliberately.
6. **Independent least-privilege credentials.** Use protected vault/agenix runtime credentials with a narrowly authorized Forgejo service identity and GitHub read access appropriate to selected source visibility. The operator approved a temporary scoped administrative bootstrap identity, issued through supported native CLI solely to authenticate OpenTofu. After verifying permanent human/service ownership, automation removes its membership and deletes that identity/token. Password and proxy authentication stay disabled; no standing provisioning-admin token is retained. Partial cleanup without a permanent owner fails closed for managed recovery. Verify actual Forgejo token/namespace privileges; do not default to an unrestricted admin token. If private upstream authentication requires credentials persisted inside Forgejo, treat its database as sensitive and document rotation/revocation.
7. **Bounded operational model.** Prevent overlapping runs, persist state atomically, retry transient failures without duplicating imports, and isolate individual repository failures. Journal summaries flow to Loki. Reuse existing Prometheus/Grafana paths for last-success, reconciliation failure, mirror error and synchronization age; stale thresholds must reflect the configured mirror interval.
8. **Explicit Git completeness.** Verify LFS behavior using the installed Forgejo mirror support and a fixture with LFS when relevant; implement supported LFS transfer for eligible sources that use it or surface a blocking incompleteness status. Submodule references remain unchanged and are documented as requiring separate access/mirroring, not rewritten silently.

## Risks / Trade-offs

- [Large initial imports exhaust disk or API quota] → Review inventory, bound concurrency/timeouts, monitor capacity, and honor rate limits.
- [Source rename is mistaken for a new repository] → Stable IDs and collision checks; non-destructive operator review.
- [Private source becomes visible] → Force-private destinations and tested membership restrictions; private inclusion is opt-in.
- [Credentials cannot be scoped as expected] → Verify installed API authorization and stop for an explicit least-privilege decision.

## Migration Plan

Introduce disabled-by-default module/service, tests, protected credentials, and policy; run report-only discovery for the requested owners. Review inventory and conflicts, then deploy targeted Habiki configuration and enable reconciliation. Verify initial imports, a repeat run, and later native mirror updates. On rollback disable the timer/reconciler without deleting repositories/state; suspend native polling explicitly if required, and revoke only the dedicated credentials. Do not downgrade Forgejo or change unrelated routes.

## Open Questions

- Operator approval is needed before including private repositories, forks, or archived sources beyond the conservative defaults.
- The approved `gh-` organizations, service membership and runtime credentials are provisioned. Habiki now has 35 healthy private mirrors, 192 exclusions and no current errors. The Forgejo token is vault-backed and the temporary bootstrap is removed; no GitHub credential is used.
- The operator approved the unchanged inventory, hourly discovery/native polling, three-hour freshness threshold and existing 500 GiB reserve. Production LFS is enabled; both native LFS errors and missing-object warnings block acceptance. LFS/workspace/growth remain unbounded.
- Live autonomous production propagation and explicitly approved stale-state/recovery verification passed on 2026-10-22; see `acceptance.md`. All 2,699 branch/tag refs matched after native polling. The temporary one-second stale threshold was restored to 10,800 seconds and current errors returned to zero.
