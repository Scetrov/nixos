## 1. Record the deferral decision

- [x] 1.1 Add a short decision note under `docs/` (e.g. `docs/dependency-track-oidc-autologin.md`) capturing: DT 4.14.5 has no auto-redirect setting (API `ALPINE_OIDC_*` / frontend `OIDC_*`), upstream #1855 is open, the two rejected alternatives and why, and the re-evaluation triggers
- [x] 1.2 Comment on GitHub issue #24 with the deferral decision, the evidence summary, and the re-evaluation triggers so the issue is tracked, not forgotten

## 2. Verification

- [x] 2.1 Confirm the DT stack on habiki is untouched (no NixOS config, image, Caddy, or Authentik changes) and that DT login still works via the OIDC button
- [x] 2.2 Run `openspec validate defer-dependency-track-oidc-autologin --strict` and archive the change per the AGENTS.md workflow
