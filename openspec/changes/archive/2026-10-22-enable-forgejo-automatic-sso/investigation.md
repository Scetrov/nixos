# Automatic SSO feasibility investigation

## Verified baseline (2026-10-22)

Read-only checks against Habiki confirmed:

- `forgejo.service` is active and runs Forgejo **16.0.6** (Go 1.26.8).
- Native authentication source ID `1`, name `authentik`, type OAuth2, is enabled.
- Anonymous `GET /` returns the public landing page (200), with a login link;
  `REQUIRE_SIGNIN_VIEW` does not make that landing page initiate OIDC.
- Anonymous repository navigation returns 303 to `/user/login`.
- `GET /user/login` returns the login page (200).
- `GET /user/oauth2/authentik` returns 307 to the existing Authentik
  authorization endpoint with state and an S256 PKCE challenge. No callback was
  completed and no production configuration or database was changed.

## Matching upstream evidence

All source links below target the installed `v16.0.6` release:

- [Example configuration](https://codeberg.org/forgejo/forgejo/src/tag/v16.0.6/custom/conf/app.example.ini):
  `[oauth2_client]` offers registration, scopes, username, avatar, and account
  linking settings, not first-visit automatic provider selection.
  `ENABLE_AUTO_REGISTRATION` creates accounts; it does not initiate login.
  `LANDING_PAGE` can change root entry but does not replace protected-route login.
- [Login/logout handlers](https://codeberg.org/forgejo/forgejo/src/tag/v16.0.6/routers/web/auth/auth.go):
  `SignIn` renders the provider-selection page. `autoSignIn` can initiate silent
  OIDC only with an existing valid SSO remember-me token; it does not solve a
  fresh browser's first visit. Existing signed sessions use native redirect
  handling. `SignOut` clears the Forgejo session and redirects to `/`.
- [OAuth handlers](https://codeberg.org/forgejo/forgejo/src/tag/v16.0.6/routers/web/auth/oauth.go):
  `SignInOAuth` accepts `redirect_to` through native redirect-cookie handling.
  Callback failures can redirect back to `/user/login` with a flash error;
  blindly redirecting that route would retry failed authentication.

## Feasibility gate / approved decision

No native first-visit auto-selection setting was found in the matching source.
The supported source-specific entry URL alone does not satisfy both direct
navigation and dashboard entry, and is not a substitute for logout handling.

The smallest apparent extension is narrow Caddy browser-entry routing to the
existing native OAuth endpoint, with root-entry handling, preservation of native
return destinations and signed sessions, and explicit logout/error exclusions.
The operator explicitly approved narrow redirects with logout/error guards.
The candidate was subsequently reproduced in the disposable native/browser
fixture and deployed through the targeted Habiki path. Do not replace it with a
blanket `/user/login` redirect: that misses root entry and can retry callback
failures or immediately sign a user back in after logout. No Forgejo source
patch, new gateway, or production dependency was introduced.

## Secure host-side recovery

Administrative SSH and sudo remain independent of Forgejo/Authentik browser
login. Use the running unit's `ExecStart` to locate the installed Forgejo binary
(it is not on Habiki's system PATH). Run native CLI commands as `forgejo` with
`GITEA_WORK_DIR=/var/lib/forgejo` and
`--config /var/lib/forgejo/custom/conf/app.ini`.

The following read-only invocations were verified using that binary:

- `forgejo admin auth list` lists the existing source without printing its secret.
- `forgejo admin auth update-oauth --help` exposes source-ID, discovery URL,
  required-claim, group-claim, and admin-group repair options.

For recovery, repair the declarative identity/source configuration rather than
editing SQLite or enabling normal password login. Any identity repair must use
`scripts/tofu.sh`; then run `./scripts/play.sh --limit habiki --tags forgejo`.
The existing preStart reconciler restores the managed source using runtime
systemd credentials. For an Authentik outage, restore the identity service first;
the CLI is an administrative repair path, not an alternative browser login.
Never print source configuration, pass secrets in command arguments, or remove
the group restriction to regain access. Mutating recovery has **not** been tested.

## Validation and remaining evidence

See `acceptance.md` for completed disposable browser/protocol coverage, quality
gates, successful deployment and restart-persistence checks, and the remaining
operator-deferred live authenticated acceptance. Issue #23 remains open. Existing
staged work was preserved.
