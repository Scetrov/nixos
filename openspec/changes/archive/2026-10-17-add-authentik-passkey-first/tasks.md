## Scope and Progress

This task list supersedes the earlier 24-task plan following the operator's scope reduction. Completed discovery/configuration/regression work is consolidated below, not newly performed. Removed acceptance obligations are deferred, not marked passed. See `evidence.md` for historical outcomes. OpenSpec edits do not authorize implementation changes or production deployment.

The operator subsequently confirmed the live baseline passkey paths, application
return, and main-page password/MFA fallback, but rejected username-first entry
and browser Back as the desired UX. Native-only investigation of explicit-first
prompting plus visible fallback is authorized; further implementation/live
changes require solution review. Task 2.4 captures this new design gate. Task
4.2 remains open for revised UX acceptance, not because the baseline fallback
is still untested.

## 1. Preserve the verified baseline

- [x] 1.1 Record verified server/provider support, existing brand ownership, baseline fallback/MFA, application flow references, and RP identity. (Consolidates former 1.1–1.2.)
- [x] 1.2 Confirm helper/callers explicitly retain `default-authentication-flow`; preserve recovery routing and do not redesign admin/token repair. (Consolidates former 1.3 and 2.5.)

## 2. Keep configuration focused

- [x] 2.1 Add default-off native candidate authentication resources and trusted-success bindings, reference existing fallback stages, and retain existing brand ownership without changing application authorization. (Consolidates former 2.1 and 2.4; browser acceptance remains separate.)
- [x] 2.2 Reconcile existing work in progress with the reduced scope: no passkey CSS/JavaScript, no helper-routing redesign, and no new enrollment flow unless an actual compatibility gap requires it. Preserve existing credentials and enrollment; defer unnecessary resources without deleting live credentials.
- [x] 2.3 Retain focused configuration and helper regressions for required UV, trusted current-flow success, fallback/MFA, default-off selection, explicit helper routing, and safe diagnostics. (Consolidates former 3.1–3.2; does not claim live repair or browser acceptance.)

- [x] 2.4 Review and promote the verified same-flow passkey-first design with visible password/MFA fallback and retained return context. Preserve existing global system settings/footer links and obtain solution/apply approval. Production configuration and the unselected live revision are now updated; no custom UI was introduced.

## 3. Verify the configuration change

- [x] 3.1 Isolate the observed positive-login harness races and demonstrate reliable local login from actual production configuration: automatic passkey entry without username/password/redundant MFA, invalid/insufficient-UV and forged-marker rejection, password/MFA success/denial, visible cancellation fallback, return preservation, and sequential-plan isolation. Conditional UI is not configured in the revised fallback stage, avoiding another passkey prompt. Three consecutive production-text suites pass; historical outcomes remain recorded without claiming an upstream conformance or hardware certification.
- [x] 3.2 Run focused tests and configured pre-commit gates, wrapper formatting/validation, and a fresh wrapper plan after CSS removal/scope reconciliation. Review for unrelated drift and secrets; do not rely on the superseded CSS-changing plan.

## 4. Provision and activate with approval

- [x] 4.1 Obtain candidate-provisioning approval, verify working independent fallback access and retain an authenticated admin session, then apply only the reviewed unselected candidate through `scripts/tofu.sh`.
- [x] 4.2 Verify the reviewed candidate's passkey login, visible cancellation fallback/password/MFA, and application return. In response to the revised checklist the operator reported functionality works, with only the misleading shared heading failing. A neutral native heading was reproduced/fixed in containers, applied through a title-only plan, and confirmed in the live fallback challenge. Prior client reports are Firefox + KeePassXC and Firefox on Windows + Windows Hello; the revised report did not restate client versions or application name. No broader device/recovery certification is claimed.
- [x] 4.3 Obtain separate activation approval, persistently select the candidate through a reviewed wrapper plan/apply, and verify routing/drift. The operator confirmed post-activation passkey/fallback/MFA/application-return smoke checks with Firefox + KeePassXC. Grafana/Loki review found zero matching server-error/exception/5xx entries; observed warnings were native policy stage-skip reevaluations. The final full wrapper plan is clean. Rollback selection remains false; no restart/rebuild or production rollback drill was required.

## 5. Document and finalize

- [x] 5.1 Align `docs/authentik.md` and `evidence.md` with the native UX, tested clients, preserved settings/credentials/fallback/admin/recovery routes, no new enrollment need, persistent true activation/false rollback, actual live results, and truthful unverified/deferred areas.
- [x] 5.2 Run final configured checks, review/stage the 21 scoped files, sync the six-requirement main capability spec, and archive this change before final commit. Gitleaks, all configured gates, focused tests, syntax/format/provider checks and strict spec validation passed. Three unrelated staged handoff deletions are excluded from the signed attributed commit.
