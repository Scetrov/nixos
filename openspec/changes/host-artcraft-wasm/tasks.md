## 1. Build and publish static packages

- [ ] 1.1 Confirm the shared access group with the operator; record the thirteen source revisions, source SHA-256 checksums, official icon provenance and compatible pinned build tooling, checking release currency and the seven-day update policy.
- [ ] 1.2 Add a small explicit build inventory and targeted Ansible build/publication flow using reviewed upstream packaging entrypoints in an isolated, unprivileged environment on Habiki; include complete assets, unchanged-input reuse, failed-build preservation and one-version rollback.
- [ ] 1.3 Compile and check all thirteen static packages at their intended path prefixes; report any upstream build blockers without silently dropping editors or adding backend services.

## 2. Wire existing hosting and identity infrastructure

- [ ] 2.1 Add the ArtCraft Caddy virtual host and required local-networking/device-host aliases, including auth-before-file-serving, outpost callback routing, trailing-slash redirects, correct MIME/cache behavior, missing-file 404s and existing TLS/logging integration.
- [ ] 2.2 Add the shared Authentik proxy provider, hidden enforcement application, approved group binding and embedded-outpost membership; add thirteen launcher-only applications with matching visibility bindings and individual launch URLs through OpenTofu.
- [ ] 2.3 Deploy the thirteen official icons through existing local branding automation, connect their metadata references, and expose a targeted ArtCraft deployment tag with brief build, deployment and rollback instructions.

## 3. Validate and deliver

- [ ] 3.1 Add focused regression checks for the thirteen routes/tiles/icons, auth ordering, asset MIME/cache behavior, missing paths, unchanged-input reuse and preservation/rollback of published packages; run applicable NixOS, Ansible, OpenTofu and pre-commit gates, using `scripts/tofu.sh` for every OpenTofu invocation.
- [ ] 3.2 Deploy with Habiki/component targeting and verify DNS/TLS, anonymous and unauthorized denial (including direct assets), authorized access, callback return paths, fail-closed outpost behavior, tile visibility and local icon delivery; confirm unrelated applications are unchanged and Caddy requests reach existing log collection.
- [ ] 3.3 Smoke-test browser initialization and a basic local interaction in every editor, checking fonts/assets and any necessary browser-security headers; exercise failed-candidate preservation and rollback through automation.
- [ ] 3.4 Record validation evidence and unresolved blockers truthfully; after successful acceptance, archive this OpenSpec change before the final signed commit/PR, check for secrets and stage all required implementation files.
