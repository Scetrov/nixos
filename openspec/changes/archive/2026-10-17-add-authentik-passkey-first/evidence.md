# Passkey-first discovery and acceptance evidence

## Current Status and Scope

The current proposal, design, spec, and 13-task list supersede the earlier
24-task acceptance programme and the subsequent 12-task scope reduction.
All 13 tasks are complete and this change is archived. The accepted native flow is activated with persistent source selection, post-activation
Firefox + KeePassXC passkey/fallback/application-return acceptance, and a clean
full wrapper plan. The shared heading is neutral, and fallback is visible without
browser Back. Historical acceptance statements below are not current gates;
see the final activation and release-check records.

Required acceptance is native passkey login with required UV and no redundant
password/MFA, working existing fallback including cancellation, unchanged
administrator/recovery routing, one actual existing passkey/browser check, one
representative application return, reviewed wrapper plans, and separately
approved provisioning/activation with documented rollback.

Deferred rather than failed or passed: three-class hardware certification,
comprehensive recovery/expiry/abuse audits, live token repair for unchanged
routing, exhaustive legacy migration and upstream assertion conformance,
mandatory restarts/rebuilds, and production rollback drills. New enrollment
resources require a demonstrated compatibility need; existing compatible
passkeys are the default path. Existing useful tests need not be discarded.

Historical positive-login failures were investigated and the reproducible CDP/
identity-polling races fixed; current production-text suites and live acceptance
pass. Historical failures or unattributed causes are retained below, not rewritten
as successful tests or universal upstream guarantees. Earlier scope changes,
task counts, incomplete-status notes, and superseded broader gates are historical
snapshots, not the final release status.

## Scope reconciliation during resumed implementation

Task 2.2: removed the three unnecessary production enrollment resources from
`terraform/authentik-flows.tf`. No existing-credential compatibility gap has
been demonstrated. Existing production enrollment and credentials are unchanged;
no production apply was performed. Synthetic authenticated enrollment remains
only in the disposable browser runner, to seed its test credential. Regression
checks now prevent production enrollment resources from being reintroduced
without revisiting this decision. Custom passkey CSS/JavaScript remains absent;
helper/caller routing remains on `default-authentication-flow`.

The standard Bubblewrap launcher ran `python3 -m unittest discover -s
scripts/tests -p 'test_authentik*.py'`: **27 tests, 26 passed, one opt-in skip**,
exit 0. Network was isolated and only this repository was writable. This is
configuration/helper evidence, not a browser-reliability result. The browser
suite was subsequently rerun with renewed operator approval as recorded below.
A fresh remote plan and production acceptance have not been run in this session;
local fixture approval does not authorize production access.

`docs/authentik.md` now describes native presentation, fixture-only enrollment,
the single existing-client acceptance requirement, unchanged fallback/admin/
recovery routing, and persistent true/false activation/rollback selection.
Actual operator client results and activation evidence remain unavailable.

### Resumed local browser verification — blocked

The operator explicitly renewed permission for
`RUN_PASSKEY_BROWSER_TESTS=1 python3 scripts/tests/run_authentik_passkey_browser.py`
outside Bubblewrap: rootless Podman, host Chromium, pinned image pulls if
needed, one localhost-only dynamic port, synthetic credentials, and cleanup.
No host credential mounts, production credentials, plans, or applies were
included. This host-side exception removes the standard command sandbox's
network isolation; fixture containers retain their internal network and the
browser retains its background-networking/DNS restrictions.

Six fresh disposable runs were performed after production enrollment removal:
**four complete passes and two failed suites**. Passed runs exercised native
explicit login without redundant password/MFA, negative assertions, forged
markers, fallback/MFA, cancellation return, conditional feature detection,
default-off provisioning, and fixture activation/rollback. Real OS conditional
selection remains unverified, not an additional device-matrix requirement.

- Run 3 failed explicit-passkey acceptance with `CDP Runtime.evaluate failed`.
  The native redirect had occurred; subsequent diagnostics showed a session
  cookie and HTTP 200 from the current-user endpoint. This suggests, but does
  not establish, a harness navigation/context race. No authentication fix is
  claimed.
- Added fixed allowlisted CDP error categories (context destroyed/missing,
  target navigated, unclassified), without echoing arbitrary protocol payloads.
  Two subsequent suites passed.
- The third diagnostic suite failed existing fallback/MFA: the correct fixture
  password was submitted, WebAuthn returned a credential, but validation stages
  repeated until timeout and current-user status remained HTTP 403. No client
  JavaScript exception was recorded. Cause remains undiagnosed; do not waive
  this observed fallback regression as deferred conformance work.

All six runs reported removal of fixture containers, volume, network, synthetic
state/credentials, and browser profile. No production writes occurred. Task 3.1
remains incomplete, activation remains blocked, and investigation is paused
for operator guidance. The new fallback failure needs an isolated reproduction
before any remediation; neither retries nor HTTP 200 diagnostics alone prove
reliable scoped acceptance.

### Live candidate preparation — approved, not applied

After reviewing the local failures, the operator approved a fresh production
wrapper plan and candidate-only provisioning provided there are no unrelated
changes. Activation was not approved. The operator confirmed working independent
`default-authentication-flow` login and a retained authenticated admin session.
Known local failures remain unresolved; live candidate testing is investigation,
not acceptance or permission to select it as the default.

The installed pre-commit hook is present. `pre-commit run --all-files` passed
all configured gates, including Gitleaks, Authentik regressions, and formatting.
`scripts/tofu.sh -- fmt -check terraform` passed; wrapper validation reported
valid configuration, zero errors and zero warnings.

A fresh full wrapper plan with explicit
`-var=authentik_passkey_first_enabled=false` reported **13 additions, one update,
zero removals**. All additions are candidate authentication flows/stages/bindings/
policy resources; the update is `authentik_brand.default.branding_custom_css`.
A second read-only wrapper plan confirmed the CSS field changes while
`flow_authentication` does not. Raw plans/state were processed in memory and
not saved; arbitrary response values and credentials were not printed.

No apply occurred: the existing brand CSS change is outside the approved
candidate-only scope. Provisioning is paused pending a decision to isolate
candidate resources or investigate/reconcile the brand styling drift. The
previous CSS-changing historical plan is not used as deployment approval.

### Unselected live candidate provisioned

The operator chose a candidate-only targeted wrapper plan/apply rather than
reconciling unrelated brand styling. The fresh targeted plan contained exactly
**13 creates, zero updates, zero removals**. All targets were the resource
addresses declared in `terraform/authentik-flows.tf`; no enrollment or brand
resource was targeted. The only plan warning was resource targeting.

The approved wrapper apply explicitly set
`-var=authentik_passkey_first_enabled=false` and created those 13 resources:
**13 additions, zero changes, zero removals**, exit 0. The wrapper refreshed
`src/generated-secrets.yml` in encrypted form as its normal post-apply action.
No raw secret-bearing plan/state artifact was saved. OpenTofu warned that
targeted applies may be incomplete, so both targeted and full follow-up plans
were reviewed rather than claiming the entire configuration was converged.

- Follow-up candidate plan: **zero changes**, exit 0.
- Follow-up full plan: **zero additions, one brand update, zero removals**;
  the previously identified, deliberately excluded brand CSS drift remains.
- Live unauthenticated current-brand API returned
  `flow_authentication = default-authentication-flow` after apply.
- Candidate URL: `https://identity.net.scetrov.live/if/flow/passkey-first-candidate/`.

Tasks 3.2 and 4.1 are complete. Task 3.1 remains unresolved; task 4.2 awaits
actual operator/browser/passkey acceptance, fallback/MFA and cancellation, and
one representative application-return check. No passkey material is requested
or retained. Testing the live candidate is investigation, not a waiver of known
failures or approval to activate it. No default selection change, credential
mutation, service restart, or activation has occurred.

### Operator live passkey result — Firefox + KeePassXC

The operator reported **“Firefox + KeePassXC = Passkey Only Login”** after
being directed to the explicit live candidate. This records successful existing
passkey-only login with Firefox and KeePassXC, not universal client support.
Browser/manager versions and operating system were not supplied. No credential
material or new enrollment was requested or recorded.

The native entry page initially appeared to require a username; the operator
subsequently found the passkey action. Native secondary placement remains an
accepted presentation limitation. Candidate password/MFA fallback, cancellation
return, and representative application return have not yet been reported as
passed. Task 4.2 therefore remains incomplete, as does local failure diagnosis;
no activation is authorized or performed by this result.

### Operator live passkey result — Firefox on Windows + Windows Hello

The operator initially reported cancellation/timeout with no Windows Hello
prompt despite an existing registered Hello credential. They then found an
already-open Google passkey window and reported that authentication via Windows
Hello in Firefox now succeeds. This supersedes the initial failed attempt as
the current client outcome; no Authentik configuration change was made between
those attempts. The overlapping prompt is an operator-reported explanation,
not an independently established server or browser root cause.

Record **Firefox on Windows + Windows Hello: successful authentication** using
the existing credential. Firefox/Windows versions were not supplied. This does
not resolve the separate intermittent local fixture failures or establish
candidate fallback, cancellation return, or application-return acceptance.
Default selection and activation approval remain unchanged.

### Operator live application-return result

The operator confirmed that application login/return works. Record this as an
operator-reported successful representative application-originated login and
return; the application name was not supplied. This does not change application
authorization or default flow selection. Candidate password/applicable-MFA
fallback and cancellation return remain awaiting explicit confirmation, so
task 4.2 is not yet complete. Local fixture failures remain unresolved and
activation has not been approved or performed.

### Operator live cancellation result — fallback not demonstrated

The operator reports that cancelling the passkey attempt does not return to
fallback; the page instead offers **“Retry authentication”**. Record this as
an unsuccessful cancellation-to-fallback check, not a passed native fallback
path. Whether browser Back returns to the candidate identification page and
allows successful password/applicable-MFA login without a loop has not yet
been established. The current design permits browser Back only if verified
usable. Task 4.2 remains incomplete and activation remains blocked. No
configuration change is justified by this report alone; first establish the
precise navigation behavior and browser/authenticator used.

### Revised UX goal and native-only investigation

The operator confirmed the main candidate allows fallback to email/username,
password, and MFA. This supersedes the earlier unverified baseline fallback
status. They nevertheless want **passkey prompt first, then a visible fallback
option on cancellation/failure**, not username-first entry or browser Back.
The operator approved revising the goal and investigating native configuration
only. No custom UI or further live changes are approved without solution review.
Current artifacts now reflect this revision; task 2.4 adds the design gate and
task 4.2 remains open for revised UX acceptance. The current task list has 13
tasks, with seven complete; prior counts above are historical.

#### Findings against pinned primary sources

1. **Automatic explicit prompting exists already.** The native validation
   component calls `tryAuthenticating()` when its challenge changes. Its
   cancellation/timeout handling sets a client-side error, clears the loading
   state, and renders Retry. It does not submit a cancellation transition to
   the server. Therefore merely adding a later fallback stage or changing an
   invalid-response policy does not handle this local cancellation.
   [2026.8.3 WebAuthn component, lines 89–150](https://github.com/goauthentik/authentik/blob/version/2026.8.3/web/src/flow/stages/authenticator_validate/AuthenticatorValidateStageWebAuthn.ts#L89-L150).
2. **“Select another authentication method” is not username fallback.** The
   validation parent supplies the back button only when multiple device
   challenges exist; the base component resets the device picker. With no
   pending user, the server generates a generic WebAuthn challenge, not a
   password/device selection. Do not weaken validation to manufacture fallback.
   [Validation parent, lines 312–327](https://github.com/goauthentik/authentik/blob/version/2026.8.3/web/src/flow/stages/authenticator_validate/AuthenticatorValidateStage.ts#L312-L327),
   [device base](https://github.com/goauthentik/authentik/blob/version/2026.8.3/web/src/flow/stages/authenticator_validate/base.ts),
   [server stage](https://github.com/goauthentik/authentik/blob/version/2026.8.3/authentik/stages/authenticator_validate/stage.py).
3. **Conditional UI is autofill, not equivalent to an immediate modal.** The
   identification controller uses `mediation: "conditional"` only after a
   client feature check. Keeping it enabled does not implement the revised
   passkey-first experience for every tested client.
   [Pinned conditional controller](https://github.com/goauthentik/authentik/blob/version/2026.8.3/web/src/flow/stages/identification/controllers/WebauthnController.ts).
4. **A native fallback link is a plausible configuration seam.** The pinned
   frontend renders footer links as normal anchors from `brand.uiFooterLinks`.
   The pinned server public brand serializer derives those links from the
   current tenant's settings and marks the public field read-only. In this
   version, changing brand attributes is not the documented writable owner.
   The pinned provider supports `authentik_system_settings.footer_links`; no
   such resource is currently declared in repository Terraform files. Current
   unversioned branding docs describe per-brand configuration, so rely on the
   pinned source/provider rather than assuming that newer UI is available.
   [Native footer renderer](https://github.com/goauthentik/authentik/blob/version/2026.8.3/web/src/flow/components/ak-brand-footer.ts),
   [pinned public brand API](https://github.com/goauthentik/authentik/blob/version/2026.8.3/authentik/brands/api.py#L94-L150),
   [provider system settings](https://github.com/goauthentik/terraform-provider-authentik/blob/v2026.8.0/docs/resources/system_settings.md).
5. **Application return remains unproven for this design.** Footer anchors
   render their configured `href` directly; they do not copy the current flow's
   application-return query. The native cancellation endpoint can clear the
   current plan and redirect to an explicitly supplied relative `next`, but
   this does not demonstrate preservation of the original application's return
   target when switching flows. Do not mark this solved or hardcode a user/
   application-specific authorization URL.
   [Footer anchor](https://github.com/goauthentik/authentik/blob/version/2026.8.3/web/src/flow/components/ak-brand-footer.ts#L49-L60),
   [CancelView, lines 491–514](https://github.com/goauthentik/authentik/blob/version/2026.8.3/authentik/flows/views/executor.py#L491-L514).

**Candidate design for review:** native explicit-first flow with a native
“Use username/password instead” footer link to preserved fallback. Benefits:
no custom frontend code; a visible exit after cancellation without browser
history. Unresolved: global footer footprint and ownership, preservation of
all existing system settings/links, safe flow cancellation, and original
application-return context across fallback. A local proof is needed before
implementation/deployment approval; no native-only complete solution is claimed.

Only OpenSpec artifacts are changed for this revision. No production/API writes,
new resources, browser instrumentation, or authentication setting changes were
performed during the investigation. The previous default and live candidate
remain unchanged. Earlier local fixture failures are not waived by these
findings or by operator-reported baseline successes.

### Disposable native-footer proof — return-context blocker reproduced

The operator approved testing the candidate design in the existing disposable
fixture, with no live changes. The opt-in command is:

```bash
RUN_PASSKEY_BROWSER_TESTS=1 PASSKEY_NATIVE_FOOTER_PROOF=1 \
  python3 scripts/tests/run_authentik_passkey_browser.py
```

The proof mode modifies only generated local fixture configuration: it selects
the explicit passkey flow in the disposable brand and sets a native system
footer link to `/if/flow/default-authentication-flow/`. Production Terraform
resources, global settings, brand selection, and credentials are unchanged.
Existing digest-pinned containers, synthetic credentials and localhost-only
networking are reused; no new dependency or test framework is introduced.

The first proof reproduced the earlier positive-login harness failure with the
specific safe CDP category **target navigated**. The native redirect had occurred
and the current-user endpoint returned HTTP 200. A narrowly scoped harness fix
now retries only `CDP Runtime.evaluate failed (target navigated)` inside existing
bounded, read-only polling. Other protocol/application errors still fail, and
session/identity assertions remain required. This isolates one harness race;
it does not explain or waive the previously observed fallback/MFA timeout.

The second proof produced:

- **PASS:** the selected native entry automatically attempts a passkey, without
  identification/password stages, and preserves a distinct same-origin return
  destination on the passkey-success branch.
- **PASS:** after simulated cancellation, the native “Use username/password
  instead” footer link is visible and reaches successful password + existing
  WebAuthn MFA, without browser Back. The current-user check succeeds.
- **FAIL:** the static footer fallback loses the original return destination.
  This is a real configuration limitation in the tested design, not a passed
  application-return test. The proof used an existing authenticated API endpoint
  with a synthetic query marker as a return sentinel; it was not an OIDC or
  proxy application integration test.

Both proof suites exited 1, with the first also reporting the harness race.
The return-context assertion remains deliberately failing in the opt-in proof;
it is not skipped or weakened. The ordinary browser suite was then run without
proof mode and passed all exercised cases (OS autofill selection remains
unverified). That single baseline pass does not establish elimination of all
historical intermittent failures. Offline focused regressions passed **23/23**;
Node syntax and whitespace checks passed before the first proof.

Each local run reported cleanup of containers, volume, network, synthetic state/
credentials, and browser profile. No production wrapper plan/apply or live API
write was performed for this proof. Task 2.4 remains blocked on a reviewed native
context-preserving fallback design; activation remains unapproved. The global
footer footprint and preservation of existing system settings/links still
require review before any production adoption.

After the proof and documentation updates, Node syntax, whitespace checks, and
all configured `pre-commit run --all-files` gates passed, including Gitleaks.
Those gates do not run the opt-in native-footer proof and do not override its
failing return-context result.

### Return-context fix verified in the disposable fixture

The operator requested fixing the native handoff; this authorized local fixture
work, not production changes. The original cross-flow static-link proof was
rerun and failed its unchanged return-target assertion. A separate opt-in
same-flow variant now provides the working alternative:

```bash
RUN_PASSKEY_BROWSER_TESTS=1 PASSKEY_NATIVE_CONTEXT_PROOF=1 \
  python3 scripts/tests/run_authentik_passkey_browser.py
```

The prototype is `scripts/tests/fixtures/authentik_native_context_proof.tf`,
not a production OpenTofu module. It is copied only into the
ignored disposable fixture directory. The production `.tf` resources and
selected live flow were not edited or applied for this fix.

#### Mechanism and trust boundary

- Keep native passkey validation, identification, packaged password/MFA, and
  session login in **one flow plan**. The native footer points back to that
  same flow with `use_password=1`; it no longer switches to another flow that
  clears the current plan/query context.
- A reevaluated initial binding policy captures `next` once in the active plan,
  not during cached planning or in an unrelated session-wide slot. It validates
  a bounded root-relative path, rejecting external/scheme-relative URLs,
  backslashes and control characters, then sets the native `redirect` context.
  A fallback query cannot overwrite the captured destination.
- The `use_password` flag can skip only optional initial passkey validation.
  Identification/password/MFA are skipped only by the existing trusted native
  current-flow success policy; failures execute protected stages. The flag is
  not an authentication-success marker. No weakened UV or MFA is introduced.
- Native plan cleanup clears the captured target. Separate completed
  transactions in the same browser were tested using native logout and plan
  cancellation. Concurrent independent login tabs are not certified.

Pinned implementation anchors: [executor plan matching/query storage](https://github.com/goauthentik/authentik/blob/version/2026.8.3/authentik/flows/views/executor.py#L164-L196),
[executor completion/cleanup](https://github.com/goauthentik/authentik/blob/version/2026.8.3/authentik/flows/views/executor.py#L395-L418),
[reevaluation marker](https://github.com/goauthentik/authentik/blob/version/2026.8.3/authentik/flows/markers.py#L35-L75),
and [native logout](https://github.com/goauthentik/authentik/blob/version/2026.8.3/authentik/stages/user_logout/stage.py).

#### Test outcomes and harness triage

Intermediate runs passed return preservation but failed the new later-login
check: one unnecessary instrumentation re-registration error, then intermittent
missing sessions during post-logout re-authentication. Native logout returns
to the selected passkey entry, so the virtual authenticator's automatic presence
had to be disabled while logging out and cancelling that new plan. The test
keeps the same browser/hardware instead of replacing the cookie jar to hide
state leakage.

A temporary fixed-category cookie probe then observed successful login cookie
issuance followed by a **current-user API response deleting the session cookie**;
no cookie was browser-blocked. The harness was polling identity before the
login redirect finished, permitting a stale response to expire the newly
issued cookie. `authenticatedRedirect()` now waits for the final same-origin
page to finish before asserting identity. It does not turn denial into success
or retry arbitrary errors. Temporary cookie probes were removed. The previously
isolated exact CDP target-navigation retry remains bounded and read-only.

After that fix:

- **Four consecutive corrected-proof runs passed**, including one after all
  temporary tracing was removed.
- **Three consecutive baseline browser suites passed**, with real OS autofill
  selection still explicitly unverified.
- The original static cross-flow design was rerun after harness cleanup and
  still failed the return-context assertion, as the expected negative control.
- Corrected proof assertions cover automatic passkey entry and return, cancelled
  prompt → visible native fallback → password/MFA → original return, later
  completed-transaction isolation, ignored replacement targets, forged-marker
  denial, wrong password and incomplete-MFA denial, invalid-signature/UV denial,
  and rejection of an external initial destination.
- **28 focused offline tests passed**, including five tests executing the exact
  fixture return policy. They cover target validation, verbatim relative OAuth
  query preservation, current-plan immutability, independent plans, and
  execution-time rather than cached capture. The pre-commit trigger now covers
  the new fixture policy too.

These are local return-path/synthetic-marker checks, not a new OIDC/proxy
integration certification. Global system-settings ownership/preservation,
production promotion and plan review, real application fallback-return testing,
and separate activation approval remain pending. The historical repeated-MFA
fixture failure's exact attribution is not established by these passes; it was
not reproduced in the final three baseline runs and is not silently waived.
All fixture runs cleaned up their containers, volumes, network, local state/
credentials, and browser profile. No production plan/apply or API write was
performed for this fix.

Final checks passed: 28 focused regressions, Node syntax, wrapper formatting,
staged whitespace, and every configured `pre-commit run --all-files` gate,
including Gitleaks. No temporary cookie-diagnostic references remain. Required
changes are staged; no commit, archive, or activation is claimed.

### Production promotion and unselected live revision

The operator requested commit/push followed by deployment. Inspection showed
that the fix was still fixture-only, so the operator chose **prepare production
configuration first**, explicitly allowed a live apply, and separately confirmed
working independent fallback plus a retained authenticated admin session before
the reviewed candidate revision was applied. Activation is still separate.

The same-plan design is now in `terraform/authentik-flows.tf`, retaining the
existing candidate UUID/slug. The previous explicit URL is preserved as a native
redirect with `keep_context=true`; its obsolete session binding was removed,
not the packaged session stage. Fallback identification no longer offers
conditional/passkey discovery, so selecting password does not restart prompting.
The duplicate prototype file and special proof modes were retired. The standard
browser runner now copies actual production flow and settings resource text;
its only additional enrollment resources remain disposable synthetic setup.
Historical proof commands above describe prior runs, not current runner modes.

Read-only API inventory found zero existing footer links and identified the
non-default `core_default_app_access=true`. `terraform/authentik-settings.tf`
adopts the existing `system_settings` singleton through a declarative import,
explicitly preserves all provider-managed baseline settings/flags, and adds the
native same-flow fallback footer. The pinned provider's settings serializer and
server ModelSerializer behavior were reviewed; fixture and live comparisons
verify that newer unexposed settings are preserved too.

The CSS drift was only a removed `trimspace()` wrapper: live CSS was 746 bytes,
declared CSS 747, equal after stripping whitespace. Restoring the pre-existing
wrapper eliminated the difference without changing styling. No passkey CSS or
JavaScript was added.

Validation before apply:

- **30 focused offline tests passed**, including the exact production return
  policy, native redirect alias, and system-settings baseline/ownership checks.
- Provider validation reported valid configuration, zero errors/warnings.
- **Three consecutive production-text browser suites passed**, covering the
  revised default entry in the fixture, old explicit URL, cancellation/footer
  fallback, password/MFA success and denial, return preservation, independent
  completed transactions, forged/replacement/unsafe targets, invalid/unknown/
  replayed/insufficient-UV assertions, and fixture rollback.
- Fixture comparisons preserved `base_url` and `impersonation_require_reason`,
  which are newer fields not exposed by the pinned provider.
- Every configured pre-commit gate passed, including Gitleaks and formatting.

The reviewed full plan was **5 additions, 7 updates, 1 import, 1 removal**.
Field review showed that the system-settings update was footer-only; the brand
was absent from the plan. Changes were limited to candidate stages/bindings/
policy, the context-preserving explicit alias, and native global footer adoption.
The operator then confirmed both access safeguards and approved that plan's
unselected-candidate apply.

`scripts/tofu.sh -- apply` explicitly retained
`authentik_passkey_first_enabled=false` and completed with the same counts,
exit 0. Its normal encrypted generated-secrets refresh completed. Live API
snapshots taken immediately before/after showed:

- Only `footer_links` changed in the entire system-settings response.
- The complete existing brand response was unchanged, including styling.
- The public brand still reports `default-authentication-flow` selected.
- The expected “Use username/password instead” footer points to
  `/if/flow/passkey-first-candidate/?use_password=1`.

The subsequent **full wrapper plan is clean: zero changes, exit 0**. No raw
secret-bearing plans/state were saved and no sensitive response values were
printed. No production users/credentials, application authorization, helper
routing, recovery routes, ports, or NixOS services were changed. Revised live
passkey/fallback/application-return acceptance and separate activation approval
remain outstanding; no final commit, push, or completed-change archive is
claimed yet. Three unrelated pre-existing staged handoff deletions are excluded
from the intended passkey commit.

### Neutral heading correction and approved activation

In response to the revised live acceptance checklist, the operator reported
successful passkey login and that the functionality otherwise works, but marked
the check failed because password fallback was still headed **“Sign in with a
passkey”**. The same response separately approved activation **after successful
checks**. No new client versions or application name were supplied; previous
Firefox/KeePassXC and Firefox-on-Windows/Windows-Hello reports remain the
recorded combinations, not a new device certification.

The misleading heading was reproduced with a new native browser assertion.
Before the fix the suite failed on that assertion; return checking afterward
also failed because the heading failure stopped submission, not because the
return-context fix regressed. The shared native flow title was changed to the
neutral **“Sign in”**, with a focused configuration guard. The complete browser
suite and all configured gates passed afterward.

A reviewed title-only full wrapper plan showed one update:
`authentik_flow.passkey_candidate.title`. The approved candidate update was
applied with selection false; an anonymous live executor request for
`use_password=1` returned native identification with `flow_info.title=Sign in`.
The subsequent full plan was clean. No custom rendering or authentication
behavior change was used to fix the heading.

With operator-reported functional acceptance and the title defect corrected,
the conditional separate activation approval was exercised. The persistent
source input is now `authentik_passkey_first_enabled=true`; its regression
expectation was updated accordingly. The wrapper fixture still explicitly tests
both unselected and selected configurations before returning to fallback.

The fresh activation plan contained **zero additions, one update, zero
removals**, solely `authentik_brand.default.flow_authentication`. The wrapper
apply started **2026-10-17T13:12:48Z**, completed with those counts and exit 0,
and retained its normal encrypted-output handling. Live verification confirms:

- Public current-brand selection is `passkey-first-candidate`.
- The normal default-authentication entry redirects to that candidate.
- The full wrapper plan using persistent source defaults has **zero changes**,
  exit 0. No temporary variable override is required to retain activation.

Existing telemetry was queried through Grafana's datasource API, sourcing its
service token from `~/env/grafana.env`, not through an interactive Loki endpoint.
Source discovery identified journal units `podman-authentik-server.service` and
`podman-authentik-worker.service`. In the initial 102-second post-activation
window, a 200-line sample contained only informational entries (112 server,
88 worker). A separate error-level/exception/traceback/HTTP-5xx query returned
zero entries, status 200. No raw log lines, request/credential payloads, cookie
values, or tokens were printed or saved. This is a bounded rollout snapshot,
not a claim of perpetual health or proof of real-client login by the agent.

Final **post-activation operator passkey/fallback smoke confirmation remains
pending** before task 4.3/final archive/commit. Persistent selection can be
restored to false through a reviewed wrapper plan/apply if checks regress;
users, devices, packaged flows and explicit helper routing are unchanged.

### Final post-activation acceptance and release checks

The operator explicitly selected **“Both pass — Firefox + KeePassXC”** for the
post-activation normal-login checklist: passkey, cancellation → visible native
password/MFA fallback, neutral heading, and application return. This is a live
operator report using the activated default, not an agent-held private key or a
substitute virtual authenticator. The application name and client versions were
not supplied; prior Windows Hello success remains separately recorded rather
than silently re-certified for every revision.

The operator also approved finalizing this named change: synchronize its new
six-requirement capability spec, archive it, and make a signed scoped commit/
push on `main`, excluding three unrelated staged historical-handoff deletions.
Host-side OpenSpec status/validation/archive execution was explicitly approved
because the CLI is outside the ordinary command sandbox. Signing and required
model/agent attribution must remain enabled.

The final full wrapper plan after live smoke checks again reported **zero
changes**, exit 0. A Grafana/Loki review from activation at 13:12:48Z through
**2026-10-17T14:38:08Z** covered 5,120 seconds:

- A recent 200-line liveness sample contained 192 informational, six warning,
  and two non-JSON/unparsed entries; this is explicitly a bounded sample.
- The separate error-level/exception/traceback/HTTP-5xx query returned **zero
  entries**, status 200.
- A warning-only follow-up query found six warnings, all the pinned native
  **binding failed re-evaluation** event used for policy-driven stage skipping.
  They were not password/MFA bypasses or evidence of service degradation.

Raw telemetry, credentials, cookies, assertions, authorization URLs and request
payloads were not retained. Persistent selection is true; rollback is a reviewed
source change to false and wrapper apply, followed by fallback verification.
No rollback, restart, credential removal, token-repair exercise, or hardware/
recovery conformance certification is claimed. Tasks 4.3 and 5.1 are complete;
final archive/staging/commit gates follow this record.

### Archive and final commit preparation

The operator-approved host OpenSpec CLI reported all artifacts complete and
strictly validated the change. The archive command synchronized **six added
requirements** into the new main capability and archived this change under
`2026-10-17-add-authentik-passkey-first`. Its sole incomplete-task warning was
the self-referential finalization checkbox containing archive itself; after
archive and final checks that checkbox was completed in this archived task file.
No unfinished implementation or failed acceptance was marked as complete.

The generated main spec's placeholder Purpose was replaced with the actual
native-authentication purpose. The configured EOF fixer removed a generated
extra trailing blank line, then all gates passed on rerun. Strict main-spec
validation passed with no warnings/errors; it emitted only informational
long-requirement advisories. Thirty focused tests, Node/Bash syntax, wrapper
formatting/provider validation and staged whitespace checks passed. Main and
delta scenarios consistently treat conditional UI as optional/configured, and
distinguish choosing password fallback from trusted-success stage bypass.

Review found exactly **21 scoped commit files** and three unrelated pre-existing
staged handoff deletions, which remain excluded and untouched. The local branch
is `main`, tracks `origin/main`, and was neither ahead nor behind its local
tracking ref before this commit. Full configured pre-commit/Gitleaks gates pass.
The final commit must remain signed and include `Co-Authored-By: gpt-6.1-sol`
(the harness-reported model) and `Co-Authored-By: Pi Coding Agent`. No unsigned
fallback or signing bypass is authorized.

This record prepares the final commit/push; it does not invent a commit SHA,
claim a push that has not happened, or modify the operator's excluded changes.

## Historical Status and Discovery

Discovery and local candidate implementation, 2026-10-16. No production
configuration writes, applies, login attempts, credential changes, or service
restarts have been performed. Applies and login/enrollment attempts were
restricted to disposable local fixtures. Production acceptance remains pending.
No raw API responses, credential identifiers, assertions, tokens, or recovery
links are retained here.

## 1.1 Server and provider compatibility

Read-only authenticated `GET /api/v3/admin/version/` reports:

- Running server: **2026.8.3**.
- Server-reported latest: **2026.8.4**. An upgrade is not part of this change;
  the latest-version response alone is not approval or security triage.
- `terraform/main.tf` pins provider **2026.8.0**. Matching upstream provider
  documentation exposes the fields below. Provider validation and the separate
  local native-browser results are recorded below; production acceptance has
  not been performed.

| Capability | Verified native configuration/implementation |
| --- | --- |
| Username-less assertion | Identification `webauthn_stage` supplies a challenge without a pending user; the server validates the assertion and identifies its credential owner. |
| Conditional UI | Identification client uses `autocomplete=\"username webauthn\"` when supported; its controller checks conditional mediation availability and calls `navigator.credentials.get` with conditional mediation. No separate provider conditional-UI boolean is documented. |
| Explicit passwordless route | Identification `passwordless_flow` exposes a native passwordless link, rendered as a secondary action. The operator accepts native presentation: username-less authentication and conditional UI are supported, but visually promoting the action is not a requirement. No custom passkey CSS or JavaScript is used. |
| Assertion user verification | Validation `webauthn_user_verification = \"required\"`; server passes `require_user_verification` to assertion verification. |
| Discoverable enrollment | WebAuthn setup `resident_key_requirement = \"required\"` and `user_verification = \"required\"`. |
| Authenticator compatibility | Setup supports optional `authenticator_attachment` and `device_type_restrictions`; do not introduce attachment/vendor restrictions. |
| Trusted success | Identification assigns the authenticated user's backend after assertion verification and records `auth_method = \"auth_webauthn_pwl\"` in the server-side flow plan. These are not query-string success flags. Candidate policies still require negative testing. |

Version-matched primary sources:

- [Provider identification](https://github.com/goauthentik/terraform-provider-authentik/blob/v2026.8.0/docs/resources/stage_identification.md)
- [Provider validation](https://github.com/goauthentik/terraform-provider-authentik/blob/v2026.8.0/docs/resources/stage_authenticator_validate.md)
- [Provider enrollment](https://github.com/goauthentik/terraform-provider-authentik/blob/v2026.8.0/docs/resources/stage_authenticator_webauthn.md)
- [Server identification](https://github.com/goauthentik/authentik/blob/version/2026.8.3/authentik/stages/identification/stage.py)
- [Assertion verification](https://github.com/goauthentik/authentik/blob/version/2026.8.3/authentik/stages/authenticator_validate/challenge.py)
- [Identification UI](https://github.com/goauthentik/authentik/blob/version/2026.8.3/web/src/flow/stages/identification/IdentificationStage.ts)
- [Conditional UI controller](https://github.com/goauthentik/authentik/blob/version/2026.8.3/web/src/flow/stages/identification/controllers/WebauthnController.ts)

## 1.2 Live configuration and rollback baseline

Read-only inventory used the deployed API schema and list endpoints for brands,
flows, stages, flow bindings, policies, providers, outposts, and blueprints.

- One brand: domain `.`, default selected; authentication flow
  `default-authentication-flow`. Brand recovery, enrollment, and user-settings
  selections are null. `terraform/authentik.tf` already declares
  `authentik_brand.default`; do not create a second brand. Verify actual state
  ownership and preserve all unrelated fields during task 2.4.
- Authentication bindings: identification (order 10), password (20), MFA
  validation (30), session login (100).
- Identification has no embedded password stage, passwordless flow, WebAuthn
  stage, recovery flow, or enrollment flow configured.
- The password binding's expression skips only when the pending user has an
  authenticated backend. The MFA binding's expression skips for the trusted
  `auth_webauthn_pwl` method. Both existing policy bindings have
  `failure_result = true` (execute the protected stage on policy failure).
- Existing MFA allows static, TOTP, WebAuthn, Duo, SMS, and email devices;
  `not_configured_action = skip`. WebAuthn assertion verification currently
  prefers, rather than requires, user verification. Preserve these existing
  fallback semantics; required UV belongs to the new passwordless branch.
- Existing WebAuthn setup prefers resident keys and user verification, with no
  attachment restriction or device-type restriction. Its setup flow requires
  authentication. Existing static/TOTP setup, password-change, and user-settings
  flows also require authentication. No recovery-designated flow was present.
- All eight providers (Dependency Track, Grafana, Home Assistant OIDC, Forgejo,
  Metrics, Home Assistant, Hermes, Miniflux) have null `authentication_flow`:
  they inherit selection rather than explicitly selecting a login flow.
- Outposts: embedded proxy (Metrics, Home Assistant, Hermes) and `proxy-outpost`
  (Hermes). Do not change their membership or application authorization.
- Packaged default authentication, WebAuthn enrollment, and brand blueprint
  instances report successful reconciliation. New resources must not mutate
  the packaged default flows. The matching packaged brand blueprint uses
  `state: created` and creates only when no default brand exists; it must not
  be treated as an unconditional overwrite of the existing default brand.
- RP ID is derived from the request hostname; origin from the absolute request
  URL. Keep `identity.net.scetrov.live` and HTTPS unchanged. Do not introduce
  another hostname or assume existing non-discoverable credentials can become
  discoverable without additive enrollment.

Rollback references: preserve `default-authentication-flow` and its stages;
restore the existing brand's authentication selection to that flow and restore
any subsequently adopted explicit references using a reviewed wrapper plan/apply.
Do not delete users, devices, or old enrollment flows. This is a recorded
baseline, **not** a completed rollback rehearsal.

Sources: matching packaged
[brand blueprint](https://github.com/goauthentik/authentik/blob/version/2026.8.3/blueprints/default/default-brand.yaml),
[authentication blueprint](https://github.com/goauthentik/authentik/blob/version/2026.8.3/blueprints/default/flow-default-authentication-flow.yaml),
and [RP/origin derivation](https://github.com/goauthentik/authentik/blob/version/2026.8.3/authentik/stages/authenticator_webauthn/utils.py).

## 1.3 Managed admin and token repair trace

- `src/roles/authentik-config/files/authentik_login.py` supports identification
  (including embedded password), password, user-login, and redirect challenges;
  it rejects other challenges, including interactive MFA. It bounds the loop
  to eight steps and checks authenticated user/session/CSRF material afterward.
- The optional flow-slug argument already exists. Every role caller explicitly
  passes `authentik_config_admin_recovery_flow_slug`, whose default in
  `defaults/main.yml` is `default-authentication-flow`. Selecting a different
  brand flow need not change this explicit target.
- `tasks/main.yml` checks the durable token first, then a bootstrap token, then
  bootstrap-account login and managed-admin login. It checks whether initial
  setup remains open rather than using setup as an authentication bypass.
- `tasks/reconcile-admin.yml` invokes the managed-admin blueprint and verifies
  existing group memberships are preserved when bearer authentication permits
  the snapshots. The role subsequently verifies managed-admin login.
- Token repair creates the service-account identity if necessary, reconciles
  its vaulted durable token through the service-account blueprint, then checks
  the durable token. These operations are not safe discovery probes and were
  **not** executed. Sensitive role calls use `no_log`.
- The role disables the upstream bootstrap account after successful repair;
  do not enable it to accommodate passkeys.
- The helper is only compatible noninteractively when the selected existing
  flow legitimately requires no unsupported challenge for that account. An
  enrolled required MFA challenge will fail closed. Do not introduce a
  password-only exception or remove MFA to make this helper succeed.
- There is no selected self-service recovery flow. Managed-admin repair is
  an operational path, not evidence of user recovery identity verification,
  expiry, or abuse controls. Operator clarification and acceptance are needed.
- Discovery identified helper failure paths echoing upstream bodies/errors.
  Task 3.2 now removes those diagnostics and covers redaction using synthetic
  markers. Supported identification/password/session behavior and the explicit
  fallback-flow target are preserved.

## Outstanding operator inputs and acceptance gates

The operator confirmed availability of all three real authenticator classes:
platform authenticator, physical roaming key, and passkey manager. Browser/OS,
key model, manager name, and existing-credential migration cases remain to be
specified, so task 1.4 remains pending. Availability is not a passed test.
Unavailable hardware checks must remain blocked, not pass by substitution with
virtual authenticators.

The operator selected preservation of existing operator-assisted recovery, not
new self-service recovery. Its actual identity checks, authorization, and
lost-authenticator procedure still need to be described and verified.

**Correction after operator clarification:** passkeys are already enrolled;
the requested change is passkey-first, not passkey-only. MFA enrollment does
not prove the existing repair path is broken. The previously reported design
blocker was unsupported and is withdrawn. Preserve password/MFA fallback and
the helper's explicit `default-authentication-flow` target unchanged while
implementing an unselected candidate. Verify repair compatibility before
activation without claiming that it has already passed. No new machine repair
identity, recovery mechanism, MFA exemption, or bootstrap-account reactivation
is proposed. Existing credentials should be used where compatible; additive
passkey enrollment is an option for non-discoverable credentials, not a
prerequisite imposed on all users.

## Local candidate implementation and checks

`terraform/authentik-flows.tf` adds unselected native candidate flows. It uses
references to the existing password, MFA, and session-login stages rather than
changing their settings. The identification stage retains username/email login,
adds native conditional passkeys, and links to explicit username-less passkey
validation. Only trusted native current-plan passkey success skips fallback
password/MFA stages; policy failures execute the protected stages. A separate
optional authenticated enrollment flow requires discoverability and UV without
changing existing credentials or enrollment settings.

No helper/caller routing edits are needed: all four existing role invocations
already pass `authentik_config_admin_recovery_flow_slug`, still
`default-authentication-flow`. Helper changes only redact failures and encode
the supplied slug as one URL path segment. Live repair acceptance remains
pending, not failed.

The existing brand now has a default-off
`authentik_passkey_first_enabled` selection input. Remote state discovery
confirmed `authentik_brand.default` is already managed, so no duplicate brand
or import is needed. The packaged brand blueprint is create-only. No provider
flow override changes are required. The current default remains false; for a
persistent production activation the accepted choice must be a reviewed source
change, not merely a temporary shell environment override.

### Approved execution scope

The operator explicitly approved:

- Host-side local Podman/Chromium tests with repository-digest-pinned images,
  disposable identities, localhost-only ports, no production credentials, and
  cleanup afterward. This is an exception to the ordinary no-network command
  sandbox, not permission to mount host credentials or use production users.
- Read-only wrapper state listing and plans against the existing backend and
  providers, including initialization. Credentials remain in memory; no raw
  plan/state artifact is saved. No production apply is authorized.

Ordinary offline checks continue inside the standard Bubblewrap launcher,
with no network and only this repository writable. Offline helper/configuration
and fixture-wrapper tests pass: 23 tests including the existing blueprint
ownership check. Provider validation, wrapper formatting, Bash syntax, Node
syntax, and staged whitespace checks pass. The installed pre-commit hook's
full `pre-commit run --all-files` gate passes, including Gitleaks. That gate does
not run the opt-in browser suite; it must not mask the browser failure.

The gate's Python 3.14 runtime also exposed an HTTPError resource-finalizer
warning that could echo an untrusted reason. The helper now explicitly closes
HTTP failures without reading their bodies, and the regression verifies closure.

### Operator scope correction: native presentation only

The operator explicitly rejected custom CSS and complex UI workarounds. The
visual-order requirement is withdrawn. Preserve native conditional UI and the
explicit passkey link, even though Authentik 2026.8.3 presents it as secondary
to username entry. Explain that limitation rather than engineering around it.
Provisional passkey CSS, its brand-file reference, and styling diagnostics are
removed. Existing unrelated brand styling is preserved.

Resume runs reproduced the visual failure and also found intermittent positive
explicit-passkey authentication failures (assertions returned but no session).
Other runs passed that authentication case. Removing a visual requirement does
not resolve or waive this separate reliability issue; acceptance remains open.
No production changes were made.

After removing styling, sandboxed offline checks ran 27 Authentik tests
(26 passed, one opt-in skip) and three fixture-wrapper tests (all passed).
Node syntax and unstaged whitespace checks passed. OpenSpec validation could
not run in the standard sandbox because its CLI is installed outside the
sandbox runtime paths (`bwrap: execvp openspec: No such file or directory`).
No sandbox permissions were widened. Browser acceptance and the remote plan
have not been rerun after this scope correction.

### Plan review (historical; regenerate after CSS removal)

- Before adding the provisional styling: 16 additions, 0 changes, 0 removals.
- Latest plan: **16 additions, 1 change, 0 removals**. The only existing object
  change is `authentik_brand.default.branding_custom_css`, appending the scoped
  candidate styling. Authentication selection and other brand fields are
  unchanged. There are no unrelated application/user/group/credential changes.
- The provisional CSS is **not accepted** and must not be applied as a claimed
  working visual fix. No production plan has been applied.

### Real local browser results

Run with `RUN_PASSKEY_BROWSER_TESTS=1 python3 scripts/tests/run_authentik_passkey_browser.py`.
The runner starts the pinned Authentik/Postgres images on an internal rootless
Podman network, publishes only one dynamically allocated localhost HTTP port,
and provisions the actual candidate resource text through the wrapper's
`--test-fixture-dir` mode. That mode never sources production vault credentials,
uses local state under an ignored mode-0700 temporary directory, and does not
refresh production generated secrets. Synthetic fixture inputs are supplied
through dedicated environment variables. Chromium is driven via a local CDP
pipe using Node built-ins; no new package dependency is installed.

The latest run passed these real-browser checks:

- Candidate provisioning leaves the previous route selected; activation works
  in the disposable fixture only.
- Existing password login before enrollment.
- Authenticated discoverable passkey enrollment and unauthenticated enrollment
  denial, including a supplied account identifier.
- Explicit username-less passkey login without password or redundant MFA;
  exactly one valid assertion suffices.
- Invalid signatures, unknown credentials, replayed assertions, and assertions
  missing required UV are rejected without creating a session.
- Forged client success markers do not bypass password/MFA.
- Cancelled explicit prompts can use browser Back to reach working username
  fallback without a redirect loop. This does not prove a separate in-page
  fallback link exists on the native WebAuthn prompt.
- Invalid fallback password denial; valid password followed by WebAuthn MFA.
- Native conditional-UI offer/autocomplete feature-detection branches, with
  supported/unsupported availability explicitly simulated by the harness.

**Historical handoff result: 13 browser cases pass and 1 fails.** The preferred
visual passkey-action check fails.
The current brand API and browser global configuration expose the appended
CSS, but the identification shadow root does not adopt its candidate rules and
keeps the native username-first layout. The cause was not established; subsequent diagnostics found compatibility-layer
rather than native shadow styling. Investigation was stopped at the operator's
request, and the visual requirement and provisional styling were removed.
Task 2.2 and browser acceptance remain incomplete pending authentication
reliability verification and other non-visual acceptance checks.

Actual OS/browser conditional-autofill selection remains explicitly skipped
and belongs to the operator matrix. Unsupported-device enrollment,
non-discoverable-only credential migration, recovery success/denial,
representative OIDC/proxy return-to behavior, and production repair remain
unverified. These are not passed by the existing tests.

Every fixture run removed its containers, anonymous database volume, internal
network, synthetic local state/credentials, and Chromium profile. No test
aliases, persistent ports, public routes, or observability endpoints were added.
No production service restart, token repair, user enrollment, or flow apply
has been performed.

No activation is allowed until required capabilities, independent recovery
access, candidate acceptance, and explicit provisioning/activation approvals
are resolved.
