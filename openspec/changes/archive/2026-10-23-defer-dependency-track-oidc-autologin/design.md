## Context

Dependency-Track on habiki is deployed as separate pinned images (`apiserver:4.14.5`, `frontend:4.14.5`) with OIDC against Authentik (issuer `https://identity.net.scetrov.live/application/o/dependency-track/`). Today, after the browser has no DT session, the user must click the "Login with Authentik" button on the DT login page to start the OIDC code flow. Issue #24 asks for this to happen automatically.

Evidence gathered during right-sizing (2026-10-14):

- DT 4.14.5 (latest 4.x, released 2026-10-05): the API server has `ALPINE_OIDC_*` settings and the frontend image has `OIDC_ISSUER` / `OIDC_CLIENT_ID` / `OIDC_FLOW` / `OIDC_SCOPE` / `OIDC_LOGIN_BUTTON_TEXT` — **no auto-redirect setting exists** in either.
- Upstream frontend source (main): the router guards redirect unauthenticated navigations to a static Login page; the OIDC flow starts only from the button's `oidcLogin()` handler.
- Upstream enhancement [#1855](https://github.com/DependencyTrack/dependency-track/issues/1855) remains open.
- DT 5.x (5.2.0, released 2026-10-08) is a ground-up rewrite (`V5_MIGRATION.md`, new module layout); upgrading is a separate major change, not a fix for this issue.

## Goals / Non-Goals

**Goals:**

- Record a defensible, evidence-based deferral decision so the issue is not re-litigated from scratch.
- Define concrete re-evaluation triggers so the deferral expires by design.
- Leave the live DT stack untouched (current single-click-via-button OIDC, API-key automation, and recovery paths keep working).

**Non-Goals:**

- No implementation of auto-login in this change.
- No DT version upgrade (4.14.x stays; 5.x migration is its own future change).
- No Caddy/forward_auth changes to the DT routes.

## Decisions

**Deferral over the two in-scope alternatives:**

| Option | Why rejected now |
| --- | --- |
| Pinned custom frontend image with an auto-redirect patch | Forks the UI image: every upstream 4.x point release requires re-applying and re-pinning the patch. The issue text explicitly deprioritises upstream source patches, and the patch would touch login-flow code (security-relevant) in an image we maintain but do not own. Revisit only if the deferral triggers never fire and the cost of the manual click becomes real. |
| Caddy-level auto-initiation | The DT session lives in the browser (token storage), which a reverse proxy cannot reliably inspect. Any proxy redirect therefore either loops for unauthenticated browsers or fires for already-authenticated ones; the issue explicitly calls such redirects "fragile". A Caddy `forward_auth` gate can add an Authentik login requirement but does **not** remove the second click, so it fails the issue's acceptance criteria. |
| Upgrade to DT 5.x hoping for native support | 5.x is a full architectural rewrite with a documented migration path; it is not a feature upgrade and belongs in its own change with its own risk analysis. |

**Re-evaluation triggers** (any one re-opens this change):

1. A supported auto-redirect/auto-initiate OIDC setting appears in a DT 4.x or 5.x release (or upstream #1855 is closed with a merged feature).
2. The DT 5.x migration change is proposed/approved — auto-login should then be evaluated as part of that change's target architecture instead.
3. The operator decides the remaining manual click is an acceptable permanent UX cost, and wants the issue closed instead of tracked.

## Risks / Trade-offs

- [Upstream ships native auto-redirect before we notice] → Triggers are written into the issue #24 comment; the DT 5.x migration change (when started) explicitly re-checks #1855.
- [Deferral is forgotten / issue stays open indefinitely] → The issue comment states the decision and the conditions to reopen; this OpenSpec change archives the decision in-repo.
- [Users keep hitting the extra click and expect a fix] → The issue comment explains the trade-off (fragile workaround vs. supported behaviour) so the deferral reads as a decision, not neglect.

## Migration Plan

None — documentation and an issue comment only. Rollback = delete the docs note; no deployed state is affected.

## Open Questions

- None blocking. (If the DT 5.x migration is eventually started, carry over the re-evaluation of #1855 there.)
