## 1. Establish one trusted vertical slice

- [x] 1.1 Select with the operator one permitted repository/workflow/event/ref, artifact name/path, schema version and pre-created Dependency-Track target; record retention, resource bounds, polling/recovery window, and rolling/release mapping independently of #26. Treat missing production selection as an activation blocker.
- [x] 1.2 Verify deployed Dependency-Track BOM submission acceptance semantics and least-required permissions, GitHub artifact metadata/digests/pagination/rerun behavior, and current integrity-pinned package/action/schema versions; define the producer contract and smallest authorized workflow change, or document compliant existing production.

## 2. Implement bounded ingestion

- [x] 2.1 Implement explicit workflow/run/ref/event selection and bounded downloading/validation with safe single-payload handling, archive/resource limits, local schema validation without remote references, available digest verification, and no repository-code execution.
- [x] 2.2 Implement trusted UUID/version mapping with autoCreate=false, ordered per-target uploads, stale-run protection, atomic artifact/target checkpoint state, accepted-upload/token persistence (no internal processing verification), bounded retries, and documented ambiguous acceptance recovery.
- [x] 2.3 Package an unprivileged disabled-by-default NixOS oneshot/Persistent timer with locking, protected scratch/state directories, vault-backed runtime credentials, least-required egress, and existing automation for target/team provisioning; add no ingress or private CI runner.
- [x] 2.4 Add redacted journal/Loki status and existing-path Prometheus/Grafana backlog/failure/last-uploaded signals; document producer setup, inventory/version effects, token rotation, retention-gap recovery, restart semantics, and disable/rollback behavior.

- [x] 2.5 Implement the operator-selected dedicated GitHub App authentication: one App ID/private key, multiple approved installation IDs, per-repository Actions-read tokens, in-memory refresh, runtime Vault/systemd key delivery, operator setup documentation, and deterministic cross-installation/expiry/rejection tests. Leave the Grafana App unchanged.

## 3. Verify and activate

- [x] 3.1 Test trusted/untrusted workflow/ref/event/run attempts, expired artifacts, pagination/rate limits, hostile archives/JSON, digest/schema failures, mapping substitution, stale ordering, duplicates, retry/crash windows, upload rejection, and credential redaction with deterministic fixtures.
- [x] 3.2 Reproduce successful upload acceptance against a disposable Dependency-Track/test-project setup; verify no-op repeat polling, skip accepted uploads after restart, malformed artifact rejection, and isolated targets without executing source code.
- [x] 3.3 Provision the approved single target and least-privilege credentials through existing automation, review host drift and report-only discovery, then activate only the targeted private collector. Verify real upload acceptance, repeat/restart behavior, monitoring and unchanged private ingress; leave unmet live acceptance pending.
- [x] 3.4 Run strict OpenSpec validation, relevant module/collector checks and configured pre-commit gates; archive before any final commit/PR and stage only intended files.
- [x] 3.5 Map every acceptance criterion in issue #27 to recorded evidence and post a redacted closure summary with durable evidence links using gh. Close #27 as completed only when all criteria are supported, then verify the issue state; otherwise leave it open and record unmet criteria or verification blockers. Record the operator-approved scope change: internal processing verification is not collector acceptance; do not claim that original issue criterion as verified.
