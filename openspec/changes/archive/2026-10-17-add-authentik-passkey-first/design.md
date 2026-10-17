## Context

Issue #21 needs a native Authentik configuration change, not a replacement login UI or a recovery-system project. Discovery verified server 2026.8.3, provider 2026.8.0, native username-less WebAuthn, and the existing fallback flow. The existing brand is already OpenTofu-managed; packaged fallback stages should remain referenced rather than mutated.

The operator retained proportionate acceptance but, after live testing, revised the UX goal: initiate passkeys first and provide visible password/MFA fallback after cancellation or failure, rather than requiring browser Back. Investigation is limited to native configuration; no custom UI or further live changes are approved without solution review. [evidence.md](evidence.md) retains historical findings superseded by current artifacts. The revised candidate was provisioned, separately approved/selected, and operator-confirmed through normal-login smoke checks with Firefox + KeePassXC. Historical fixture failures and their investigation are retained in the evidence; current scoped suites and live acceptance pass.

## Goals / Non-Goals

**Goals:** native passwordless login with required user verification, compatible existing credentials, preserved fallback/admin routing, focused verification, and approved reversible activation.

**Non-Goals:** custom passkey CSS/JavaScript, upgrades, recovery redesign/certification, full hardware or migration matrices, forced enrollment, live token-repair exercises for unchanged routing, new test infrastructure, mandatory restarts/rebuilds, or production rollback drills.

## Decisions

### 1. Use the existing native configuration seams

Keep the dedicated authentication resources and controlled brand selection: false during initial provisioning, persistently true after accepted activation, and false for rollback. Use native identification/validation/session stages and only the bindings/policies needed for that composition. Reference existing password/MFA stages without weakening them. Preserve unrelated brand fields and existing application authorization. All OpenTofu commands use `scripts/tofu.sh`; do not add competing blueprint ownership or imperative API configuration.

The earlier candidate offered username-first identification and a secondary passkey link. The operator confirmed it worked but rejected that presentation. The accepted flow now attempts explicit native WebAuthn first; its password fallback identification does not restart conditional/passkey prompting. No universal OS-autofill support is claimed.

Reviewed and provisioned native design: keep passkey validation and protected identification/password/MFA fallback in one native flow. A native footer link to that same flow with `use_password=1` opts out only of the initial passkey attempt. A reevaluated binding policy captures the initial validated root-relative return destination in the current plan and assigns native `redirect`; the fallback link cannot replace it. No separate session-wide handoff slot, custom endpoint, or browser code is needed. Capture occurs during execution, not cached planning, and native plan cleanup ends its lifetime. Completed-transaction isolation is tested; concurrent independent login tabs are not certified.

In 2026.8.3, cancellation stays in the client and validation offers Retry; the footer remains the visible exit. `terraform/authentik-settings.tf` now adopts the existing singleton and owns the tenant-wide native footer. Read-only inventory found no previous links; all existing settings/flags, including non-default application access and unexposed newer fields, were preserved. Live before/after API comparisons confirm footer-only changes. CSS drift was an accidental missing `trimspace()` wrapper, restored without changing live styling.

The initial cross-flow design's return failure remains historical negative-control evidence. After promotion into production resource text, three consecutive full browser suites passed. The obsolete duplicate fixture/modes were retired; current tests use `terraform/authentik-flows.tf` and `terraform/authentik-settings.tf` directly. An approved full wrapper apply first revised the unselected candidate while preserving the brand. The operator then reported functional acceptance except a misleading heading; a neutral shared title fixed that issue and was verified live. Conditional separate activation approval was exercised through a brand-selection-only plan/apply, the persistent input is true, and the full plan is clean. Post-activation operator smoke checks passed with Firefox + KeePassXC; telemetry review and the final full wrapper plan passed. See `evidence.md`.

### 2. Keep the security boundary small and explicit

Passwordless validation requires user verification. A valid assertion identifies the account and creates the session without password or redundant login MFA. Any fallback-stage skipping depends only on trusted native success in the current flow, never query parameters, supplied identifiers, or credential presence alone. Retain application-specific authorization and independent step-up requirements.

Username/password fallback must remain accessible through a visible native action after cancellation or failure, with existing applicable MFA and the original application return destination preserved. Browser Back worked for the baseline candidate but no longer satisfies the revised UX goal. Do not bypass required UV, weaken MFA, delete credentials, or alter the hostname, HTTPS origin, or RP identity to satisfy presentation requirements.

### 3. Preserve existing enrollment, recovery, and automation

Try compatible existing passkeys first. Do not require a new enrollment flow merely because the earlier implementation added one. Review that work against the reduced scope; retain a new path only if a demonstrated credential-compatibility gap needs it. If retained, enrollment must remain authenticated, discoverable, and user-verified. Otherwise defer the new enrollment resources; existing enrollment is unchanged.

Keep the helper/callers explicitly targeting `default-authentication-flow`, and retain focused routing/challenge regression checks. Do not redesign reconciliation, intentionally invalidate the token, exempt an account from MFA, or enable the disabled bootstrap administrator. Live repair testing is required only if this change actually alters that path.

Preserve existing recovery routing and protections. Record known limitations rather than certifying identity checks, expiry, abuse controls, or authenticator-loss recovery as part of this change. A newly observed regression still blocks activation.

### 4. Verify our configuration, not the entire upstream product

Required checks are:

- Configuration ownership, unselected provisioning and persistent accepted selection/rollback, required UV, trusted-success gating, preserved fallback, and unchanged helper routing.
- Reliable native automatic passkey success without username/password/redundant MFA; OS conditional autofill is not a substitute or a configured requirement.
- Rejection of an invalid or insufficient-UV assertion and of forged client success state; fallback success/denial with existing applicable MFA; a visible native fallback action after cancellation, preserving application return without browser Back.
- One operator test using an existing passkey and the actual browser/device used for this deployment. Record that combination and limitations; no three-class hardware matrix.
- One representative application-originated login/return smoke test, not separate OIDC and proxy certification.

Reuse existing tests and the disposable fixture where useful. Do not add a conformance suite or expand the harness for deferred cases. If extra tests are retained and fail, triage them honestly rather than hiding failures. The observed positive-login races were isolated to CDP navigation and premature identity polling; bounded navigation handling and final-page identity assertions resolved the reproducible cases. Historical unattributed outcomes remain recorded rather than rewritten as passed tests.

## Deployment and Rollback

1. Reconcile the work in progress with this scope. Run focused checks, configured pre-commit gates, and wrapper formatting/validation. Regenerate the wrapper plan after CSS removal; reject unrelated drift and do not save secret-bearing output.
2. Obtain candidate-provisioning approval. Verify working fallback access and retain an authenticated admin session, then provision only unselected candidate configuration through the wrapper.
3. Verify the candidate with the operator's existing passkey/browser, fallback, and one representative application return. Local test success alone is not production acceptance.
4. Obtain separate activation approval. Select the candidate declaratively, apply the reviewed wrapper plan, smoke-test passkey and password/MFA fallback, and check existing authentication telemetry. A subsequent wrapper plan must show no unintended drift.
5. If authentication regresses, restore the previous selection through a reviewed wrapper plan/apply and verify fallback. Keep prior flows, users, and credentials. Document the exact rollback selection; a production rollback rehearsal or service restart is not required merely to complete this change.

## Completion and Limits

- The reviewed native flow/footer are provisioned and selected after separate approval. The neutral heading fixes the only reported revised-acceptance issue; post-activation passkey/fallback/application-return checks passed with Firefox + KeePassXC. Telemetry and the final full wrapper plan passed. Preserve the source false rollback option and archive before final commit.
- No new production enrollment is needed for tested existing credentials. Firefox + KeePassXC is the post-activation client; earlier Firefox on Windows + Windows Hello success is recorded separately.
- No current scoped acceptance blocker remains. Unattributed historical fixture outcomes, untested devices/concurrent login tabs, OS autofill, recovery certification, and live repair/restart/rollback exercises are not silently represented as certified behavior.

Unavailable optional device classes, comprehensive recovery audits, and restart/rebuild checks are not blockers under this scope.
