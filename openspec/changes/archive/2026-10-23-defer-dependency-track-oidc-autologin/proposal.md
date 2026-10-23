# Defer Dependency-Track OIDC auto-login until upstream supports it

## Why

GitHub issue #24 asks for automatic initiation of the Authentik OIDC login for Dependency-Track, removing the extra "Login with Authentik" click. Investigation of the deployment (DT 4.14.5, the latest 4.x release) shows the feature cannot be implemented the way the issue directs:

- DT 4.14.5 exposes no native auto-redirect setting — the API server property set (`ALPINE_OIDC_*`) and the frontend env set (`OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_FLOW`, `OIDC_SCOPE`, `OIDC_LOGIN_BUTTON_TEXT`) contain no auto-login option, and the upstream frontend source only initiates OIDC on a button click.
- The upstream enhancement request [#1855](https://github.com/DependencyTrack/dependency-track/issues/1855) is still open.
- The DT 5.x line (5.2.0, 2026-10-08) is a full architectural rewrite (new `api`/`apiserver`/`alpine` module split, `V5_MIGRATION.md`) and is far outside the scope of this issue.

The two in-scope alternatives were evaluated and rejected: a pinned custom frontend image with an auto-redirect patch (ongoing maintenance of a forked UI image against upstream 4.x releases, explicitly discouraged by the issue), and a Caddy-level solution (cannot reliably see the browser-held DT session, so it either produces redirect loops or only adds a gate — it does not remove the second click). The operator decision is to **defer** until a supported mechanism exists, rather than ship a fragile or forked workaround.

## What Changes

- Record the deferral decision, evidence, and re-evaluation triggers in a short note under `docs/`.
- Comment on GitHub issue #24 with the decision, the version evidence, and the conditions under which it will be revisited.
- No changes to the Dependency-Track NixOS configuration, images, Caddy routes, or Authentik application. Current single-click-via-button OIDC behaviour is retained unchanged.

## Capabilities

### New Capabilities

- `dependency-track-oidc`: Captures the Dependency-Track web login initiation contract that this deferral keeps in place — explicit user-initiated OIDC via the DT login page while no supported auto-redirect exists in the deployed DT release — plus the deferral decision record.

### Modified Capabilities

- None.

## Impact

- `docs/`: one new decision note (no operational change).
- GitHub issue #24: informational comment.
- No deployment, image, secret, or spec changes. No impact on API-key automation, machine-to-machine access, or administrative recovery.
