# Automatic Forgejo SSO acceptance — 2026-10-22

## Result

Implemented and deployed on Habiki. Live authenticated acceptance was initially
deferred, then completed when the operator confirmed: “Yes, all good.” The
deployed Firefox behavior is verified.

## Automated evidence

Matching binaries: Forgejo 16.0.6 and Caddy 2.11.7, realized from the existing
Nixpkgs package set. No production dependency or identity-client change.

```bash
export FORGEJO_TEST_BINARY="$(nix-build '<nixpkgs>' -A forgejo --no-out-link)/bin/forgejo"
export CADDY_BIN="$(nix-build '<nixpkgs>' -A caddy --no-out-link)/bin/caddy"
export CHROMIUM_BIN="$(command -v chromium)"
nix-shell -p python3Packages.playwright python3Packages.cryptography python3Packages.pyyaml --run \
  'python3 -m unittest scripts.tests.test_forgejo_sso scripts.tests.test_forgejo_private_proxy scripts.tests.test_forgejo_reconcile scripts.tests.test_forgejo_deploy scripts.tests.test_forgejo_metrics -v'
```

**14 tests passed, no skips.** The new disposable native/browser fixture verifies
signed OIDC tokens, PKCE, absent/present provider session, existing Forgejo
session, native remember-me behavior, repository deep links, external return-URL
rejection, actual CSRF-protected logout, manual retry/pause clearing, denied
access and missing group claims, invalid callbacks, expired/removed Forgejo
sessions, provider outage, manual login, token API access, actual Git smart HTTP
and SSH reads, webhook creation, health, and host-side CLI availability during a
simulated provider outage. Existing native tests cover source reconciliation,
credential rotation, and state/key persistence across restart.

`forgejo-eval.nix` verifies private ingress, disabled password/basic auth,
runtime credentials, browser-only routing, logout-cookie flags, and native
protocol boundaries. Existing real-Caddy private-ingress tests pass.

## Deployment and live evidence

- Compared static Nix module hashes with `/etc/nixos`: only `modules/forgejo.nix`
  differed before deployment. Existing staged work was preserved.
- Ansible check mode encountered an existing secrets-role tempfile/check-mode
  incompatibility (`dest` references an absent `path`). No unrelated fix was
  added. Static drift review and the actual targeted deployment succeeded.
- `./scripts/play.sh --limit habiki --tags forgejo`: exit 0;
  `ok=82 changed=13 unreachable=0 failed=0 skipped=20`.
- Confirmed channel updates, Frontier writer transitions, Headscale enrollment,
  Garage provisioning, and blanket Podman restarts were skipped. The normal
  secrets role still reads/reconciles its shared inputs.
- Forgejo and Caddy active; generated `app.ini` contains `LANDING_PAGE = login`,
  `REQUIRE_SIGNIN_VIEW = true`, and both internal/basic sign-in disabled.
- Repeated service restart through Ansible's `systemd_service` module; same
  settings persist and native source ID 1 remains enabled as `authentik`.
- Before and after restart: anonymous `/` → 303 `/user/login`; browser-metadata
  GET `/user/login` → 302 `/user/oauth2/authentik`; ordinary machine GET login →
  200; browser GET `/user/login?sso=manual` → 200; `/api/healthz` → 200;
  unauthenticated `/api/v1/version` → native 403; unauthenticated Git smart HTTP
  → native 401. Invalid OAuth callback → bounded native 500, not an auto redirect.
- Controlled production Chromium navigation from the service root reached the
  Authentik passkey sign-in flow without a Forgejo login-button click.
- Host-side native `admin auth list` succeeds independently of browser login.
  No live outage, source mutation, account creation, or repository modification
  was performed for acceptance.

## Issue #23 acceptance mapping

| Criterion | Evidence | Remaining live check |
| --- | --- | --- |
| Dashboard entry with Authentik session | Same root-entry flow; disposable present-provider-session test | Operator confirmed browser acceptance |
| Direct anonymous entry | Production browser reaches Authentik automatically | None for initiating login |
| Existing Forgejo session | Disposable signed-session test with provider unavailable | Operator confirmed browser acceptance |
| Original deep links | Disposable private repository/README path and unsafe-return test | Operator confirmed browser acceptance |
| Logout/failure/session expiry bounded | Disposable logout, denial, missing-group, callback, expiry, outage tests; live invalid callback | Operator confirmed Firefox logout/automatic-entry behavior |
| Git/API/webhook/token compatibility | Native disposable SSH, smart HTTP, token API and webhook tests; live unauthenticated 401/403/health | Existing production credentials if available |
| Local admin recovery | Runbook, native source CLI verified on Habiki; disposable outage/reconciliation tests | Operator acceptance of recovery procedure; disruptive live repair not attempted |
| Declarative persistence | Successful targeted rebuild and explicit Ansible Forgejo restart | None |
| End-to-end authentication/recovery | Complete disposable OIDC/browser/protocol test | Operator confirmed live browser flow; host-side recovery procedure documented |

## Firefox logout-pause regression follow-up

[Durable issue follow-up](https://github.com/Scetrov/nixos/issues/23#issuecomment-6350406491).

The operator reported the native provider button in Firefox after signing out;
a fresh private window redirected correctly. The browser-session logout pause
was too persistent, not a missing Fetch Metadata header. A regression using the
actual native logout UI reproduced the failure on reopening Forgejo. With the
original routing, the test failed with `A prior logout still blocks automatic SSO`.

The fix consumes the pause cookie on the first native login landing, preserving
the signed-out page while allowing the next visit/reload to initiate SSO. It also
consumes cookies left by the earlier deployment. An already-open affected login
page needs one reload to consume its old cookie, then another to start SSO.

The fixed native-browser regression passed three consecutive runs, and the full
14-test focused suite passed. A digest-pinned disposable Python container with a
cookie jar reproduced production login statuses `[200, 200]` before the fix and
`[200, 302]` afterward, confirming that the cookie is deleted on the first landing.
The targeted Habiki redeploy succeeded (`ok=82 changed=12 failed=0 skipped=20`);
Forgejo and Caddy are active. Full pre-commit and strict OpenSpec gates passed.
The operator subsequently verified the deployed Firefox behavior and replied:
“Yes, all good.” This completes the previously deferred live browser acceptance.

## Quality and finalization

Strict OpenSpec validation and configured full pre-commit gates pass (including
redacted gitleaks). Intended files are staged; unrelated pre-existing index
entries are preserved, not swept into a new commit. Change archived after task
3.2 acceptance. No commit or PR was requested or made.

The redacted acceptance mapping was posted as a
[durable issue update](https://github.com/Scetrov/nixos/issues/23#issuecomment-6350082438).
Issue #23 was subsequently verified **OPEN**.
