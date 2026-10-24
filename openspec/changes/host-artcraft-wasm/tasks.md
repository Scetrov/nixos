## 1. Download and publish official WASM bundles

The operator replaced compilation with official release downloads. The earlier completed work is recorded under implementation history below; it does not complete these replacement tasks. `All Applications` remains confirmed and does not need reconfirmation.

- [x] 1.1 Replace source/toolchain build inputs with a small explicit inventory of thirteen official GitHub WASM release-asset URLs/filenames, versions and expected SHA-256 checksums; retain verified official icon provenance, check current releases and the seven-day update policy, and record deferred release versions/dates.
- [x] 1.2 Replace the in-flight compilation flow with targeted Ansible download, checksum verification, safe extraction, package checking and atomic publication; retain unchanged-input reuse, failed-candidate preservation and one-version rollback, reuse existing validation/publication helpers where useful, and remove unused builder files, toolchain pins, build-only tests and compilation instructions.
- [x] 1.3 Download and check all thirteen official bundles and their complete runtime assets at the intended path prefixes; report missing or unusable upstream bundles without silently dropping editors, compiling replacements or adding backend services.

## 2. Wire existing hosting and identity infrastructure

- [x] 2.1 Add the ArtCraft Caddy virtual host and required local-networking/device-host aliases, including auth-before-file-serving, outpost callback routing, trailing-slash redirects, correct MIME/cache behavior, missing-file 404s and existing TLS/logging integration.
- [x] 2.2 Add the shared Authentik proxy provider, hidden enforcement application, approved group binding and embedded-outpost membership; add thirteen launcher-only applications with matching visibility bindings and individual launch URLs through OpenTofu.
- [x] 2.3 Deploy the thirteen official icons through existing local branding automation, connect their metadata references, and expose a targeted ArtCraft deployment tag with brief download, deployment and rollback instructions.

## 3. Validate and deliver

- [x] 3.1 Add focused regression checks for the thirteen routes/tiles/icons, auth ordering, asset MIME/cache behavior, missing paths, download/checksum failures, unsafe archives, unchanged-input reuse and preservation/rollback of published packages; run applicable NixOS, Ansible, OpenTofu and pre-commit gates, using `scripts/tofu.sh` for every OpenTofu invocation.
- [ ] 3.2 Deploy with Habiki/component targeting and verify DNS/TLS, anonymous and unauthorized denial (including direct assets), authorized access, callback return paths, fail-closed outpost behavior, tile visibility and local icon delivery; confirm unrelated applications are unchanged and Caddy requests reach existing log collection.
- [ ] 3.3 Smoke-test browser initialization and a basic local interaction in every editor, checking fonts/assets and any necessary browser-security headers; exercise failed-candidate preservation and rollback through automation.
- [ ] 3.4 Record validation evidence and unresolved blockers truthfully; after successful acceptance, archive this OpenSpec change before the final signed commit/PR, check for secrets and stage all required implementation files.

## Implementation history — superseded compilation approach

These checkboxes preserve work completed before the operator changed the delivery approach. They are historical, not acceptance of the download implementation; do not resume compilation.

- [x] H.1 Confirmed `All Applications`; recorded thirteen source revisions/checksums, official icon provenance and candidate build-toolchain pins under the former task 1.1. Release-asset pins still need to be established in replacement task 1.1.
- [x] H.2 Added the isolated Ansible compilation/publication flow, cache reuse and preservation/rollback unit tests under the former task 1.2. The compilation path is superseded and must be replaced in task 1.2; useful validation/publication code can remain.
