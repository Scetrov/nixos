## 1. Confirm source and API contracts

- [x] 1.1 Verify installed Forgejo migration/pull-mirror/status APIs, GitHub user/organization pagination, LFS behavior, and minimum credential permissions; review existing module/test patterns and resolve current applicable releases/hashes for any new dependencies.
- [x] 1.2 Define the three requested owner/pattern policies, conservative eligibility defaults, destination namespaces, cadence/freshness thresholds, and rename/transfer/visibility behavior; produce a report-only inventory including storage estimates and collisions, and obtain approval before production import or broader private/fork/archived inclusion.

## 2. Implement safe reconciliation

- [x] 2.1 Add a focused reconciler for paginated discovery, report-only planning, stable source identity/atomic ownership state, native pull-mirror creation, idempotency, collision rejection, and non-destructive lifecycle reporting; keep identity reconciliation and #27 selection separate.
- [x] 2.2 Add disabled-by-default NixOS service/timer configuration, single-run locking, protected runtime secrets and least-privilege accounts, bounded retries/timeouts, and startup/readiness handling without enabling Actions or new ingress.
- [x] 2.3 Add journal/Loki summaries and existing-path Prometheus/Grafana freshness/failure signals; document LFS completeness, unchanged submodule references, credential rotation, source lifecycle review, disable/polling behavior, and rollback.

## 3. Validate and roll out

The approved import stage is deployed on Habiki with 35 healthy private mirrors;
see `acceptance.md`, `investigation.md` and the historical
`report-only-inventory.json`. Provisioning, scoped three-org ownership, runtime
credentials, timer and Grafana/Loki signals are verified. On resumption the operator explicitly
approved the recorded 35 public/non-fork/non-archived sources, hourly cadence,
three-hour staleness and 500 GiB reserve conditional on safety checks. Refreshed
selection is unchanged, capacity is sufficient for the reported Git estimate,
production LFS is now enabled, and native missing-object warning/recovery plus
the production Loki path/query are verified. Autonomous production polling at
20:11:24–20:11:50 BST propagated later source commits; all 2,699 branch/tag refs
matched. The explicitly approved one-second stale-threshold test produced 35
errors in Mimir and stale logs in Loki; restoring 10,800 seconds recovered 35
healthy/zero errors without restarting Forgejo or Frontier. Task 3.3 is complete.
LFS volume remains unbounded; maintain the reserve and treat both LFS errors and
missing-object warnings as blocking.

- [x] 3.1 Test requested matching/exclusions, multiple API pages, namespace collisions, existing unrelated destinations, repeated convergence, new source discovery, rename/transfer/delete/visibility events, quota/transient failures, restart recovery, and secret redaction using API fixtures.
- [x] 3.2 Exercise native mirror creation and branch/tag updates in disposable local containers with public/private authorization and applicable LFS/submodule fixtures; repeat runs and verify private access and preserved data.
- [x] 3.3 Review approved inventory and host drift, deploy only to Habiki through targeted automation, and verify initial imports, a no-op reconciliation, later native Git updates, restart/rebuild persistence, and observable stale/failure handling; keep unverified acceptance pending.
- [x] 3.4 Run strict OpenSpec validation, relevant Forgejo tests and configured pre-commit gates; archive before final commit/PR and stage only intended files.
- [x] 3.5 Map every acceptance criterion in issue #26 to recorded evidence and post a redacted closure summary with durable evidence links using gh. Close #26 as completed only when all criteria are supported, then verify the issue state; otherwise leave it open and record unmet criteria or verification blockers.
