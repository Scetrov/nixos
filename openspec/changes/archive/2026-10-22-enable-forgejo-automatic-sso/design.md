## Context

Forgejo on Habiki uses native Authentik OIDC and private Caddy ingress. `forgejo.nix` requires sign-in, disables internal/basic password authentication, and deliberately avoids proxy forward-auth for Git/API compatibility. Identity reconciliation already creates the `authentik` source. The runbook reports Forgejo 16.0.5; verify the actual installed package and supported behavior rather than assuming current online documentation applies.

## Goals / Non-Goals

**Goals:** Automatically enter the existing OIDC flow for unauthenticated interactive browser entry, preserve sessions and supported destinations, avoid failure loops, and retain recovery and native Git/API access.

**Non-Goals:** Dependency-Track SSO, a second authentication gateway, broader user enrollment, local-password re-enablement, custom OIDC implementation, or Forgejo Actions.

## Decisions

1. **Capability check before configuration.** Inspect the installed release's configuration/source and reproduce its login behavior in a disposable local instance with a test identity provider where feasible. Prefer a native auto-login setting; do not invent an option based on another forge/version.
2. **Use the existing authentication source.** Investigation confirmed Forgejo 16.0.6 has no first-visit provider auto-selection. The operator approved narrowly scoped Caddy routing to the supported `/user/oauth2/authentik` entry. Set native `LANDING_PAGE = login` for anonymous root visits. Only interactive GET document navigation to `/user/login` is eligible; intercept only a native 200 login page, preserving native Set-Cookie headers and return-query handling. Native signed-session/remember-me redirects pass through unchanged. No Forgejo patch, gateway, or blanket forward-auth.
3. **Keep browser navigation distinct from protocols.** Require `Sec-Fetch-Mode: navigate` and `Sec-Fetch-Dest: document` on the exact login path. Git smart HTTP, API requests, webhooks, health checks, callbacks, POST login, and token operations retain native handling. A Forgejo `flash` cookie suppresses automatic retry so native callback errors remain visible. POST logout sets a secure HttpOnly SameSite=Lax `forgejo_sso_pause` cookie for the first native login landing only; the login response consumes it, so subsequent visits automatically resume SSO. The exact OAuth entry also clears the cookie. This replaces the overly persistent browser-session pause reported during Firefox acceptance. A `sso=manual` login query also suppresses automatic entry; it never bypasses authentication.
4. **Preserve recovery without adding a bypass.** Document the existing secure host-side administrator/authentication-source repair procedure. Do not reopen normal local-password authentication or add an unauthenticated public recovery route.
5. **Reuse the existing deployment path.** Keep configuration declarative and use targeted Habiki Forgejo deployment. Any Authentik changes go through `scripts/tofu.sh`; avoid identity changes if existing client configuration suffices.

## Risks / Trade-offs

- [Installed Forgejo lacks supported auto-entry] → Resolve in the first investigation task and report a blocker before expanding scope.
- [Logout immediately signs the user back in] → Explicit logout landing behavior and bounded error handling are acceptance gates.
- [Untrusted return URL becomes an open redirect] → Use native validated same-origin return destinations; reject external destinations.
- [Git/API clients receive HTML redirects] → Test protocols and route behavior, not only browser login.
- [A healthy Authentik session hides failure handling] → Test absent/expired sessions, denied users, callback errors, and provider outage.

## Migration Plan

Capture the current native login configuration and recovery procedure. Validate a disposable reproduction and focused tests, then deploy only to Habiki using the documented Forgejo target after reviewing host drift. Verify browser and protocol acceptance and restart persistence. Roll back the managed auto-entry setting/entry-point change through the same automation without deleting accounts, sessions, repositories, or OIDC state.

## Verification boundary

Reproduce the native login page before and after the routing change with disposable Forgejo and a test OIDC provider. Verify native return-cookie and `redirect_to` query handling, unsafe external destinations, signed-session redirects, flash errors, logout pause/manual retry, and protocol routes. Record any unavailable live identity/recovery checks honestly; do not close issue #23 or archive with unmet acceptance.
