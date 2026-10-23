# Dependency-Track OIDC Auto-Login: Deferral Decision

**Status:** Deferred — no supported mechanism exists in the deployed Dependency-Track release.
**Date:** 2026-10-14
**Tracked by:** [GitHub issue #24](https://github.com/Scetrov/nixos/issues/24), OpenSpec change `defer-dependency-track-oidc-autologin`.

## Decision

The request to automatically initiate the Authentik OIDC login for Dependency-Track (removing the "Login with Authentik" click) is **deferred** until a supported auto-redirect mechanism exists. The current behaviour — explicit user-initiated OIDC via the login button on the DT login page — is retained unchanged.

## Evidence (DT 4.14.5, latest 4.x)

- The DT API server exposes `ALPINE_OIDC_*` settings and the frontend image exposes `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_FLOW`, `OIDC_SCOPE`, and `OIDC_LOGIN_BUTTON_TEXT` — **neither set contains any auto-redirect or auto-initiate option**.
- Upstream frontend source (main): unauthenticated navigations are redirected by router guards to a static login page; the OIDC code flow starts only from the button's `oidcLogin()` handler.
- The upstream enhancement request [DependencyTrack/dependency-track#1855](https://github.com/DependencyTrack/dependency-track/issues/1855) remains open.
- The DT 5.x line (5.2.0, released 2026-10-08) is a full architectural rewrite (`V5_MIGRATION.md`, new `api`/`apiserver`/`alpine` module split). Upgrading is a separate major change, not a fix for this issue.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Pinned custom frontend image with an auto-redirect patch | Forks the UI image: every upstream 4.x point release requires re-applying and re-pinning the patch. Issue #24 explicitly deprioritises upstream source patches, and the patch would touch security-relevant login-flow code in an image we maintain but do not own. Revisit only if the deferral triggers never fire and the manual click becomes a real cost. |
| Caddy-level auto-initiation | The DT session lives in the browser (token storage), which a reverse proxy cannot reliably inspect. A proxy redirect either loops for unauthenticated browsers or fires for already-authenticated ones. A `forward_auth` gate can require Authentik login but does **not** remove the second click, so it fails the issue's acceptance criteria. |

## Re-evaluation triggers (any one re-opens this work)

1. A supported auto-redirect / auto-initiate OIDC setting appears in a DT 4.x or 5.x release, or upstream [#1855](https://github.com/DependencyTrack/dependency-track/issues/1855) is closed with a merged feature.
2. A DT 5.x migration change is proposed/approved — auto-login should be evaluated as part of that change's target architecture.
3. The operator decides the remaining manual click is an acceptable permanent UX cost and wants issue #24 closed instead of tracked.

## Scope note

This deferral affects web login initiation only. API-key automation against `https://dtrack-api.net.scetrov.live`, machine-to-machine access, and administrative recovery are unaffected and remain as documented in [dependency-track.md](dependency-track.md).
