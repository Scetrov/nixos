## 1. Confirm the existing integration points

- [x] 1.1 Verify Habiki's deployed Immich version and its supported runtime secret/configuration mechanism, web/mobile OIDC callbacks, local administrator bootstrap and official reverse-proxy requirements; record the concrete choices without upgrading packages.
- [x] 1.2 Confirm certificate coverage, existing hostname resolution, intended Authentik access policy and credential export/deployment ordering; reuse them without unrelated changes.

## 2. Add the minimal declarative integration

- [x] 2.1 Add the Immich Authentik OIDC provider/application with exact callbacks and existing access policy, sensitive credential outputs and the minimum existing generated-secret/Ansible/agenix wiring; reject missing/placeholder inputs and use `scripts/tofu.sh` for all OpenTofu operations.
- [x] 2.2 Update `immich.nix` to bind on loopback, disable automatic firewall opening and define its Caddy HTTPS virtual host using the existing certificate and a normal reverse proxy without forward authentication.
- [x] 2.3 Configure native OIDC from protected runtime files and retain local administrator login; automate recovery-account bootstrap using supported tooling and a runtime-managed credential, without resetting storage or migrating users.

## 3. Verify and document

- [x] 3.1 Add focused regression checks using existing test conventions for listener/firewall/proxy settings, exact OIDC callbacks/access policy and protected matching credential wiring; run relevant tests, Nix evaluation/configuration checks, wrapper-based OpenTofu validation and configured pre-commit gates without exposing secrets.
- [x] 3.2 Add `docs/immich.md` with targeted deployment commands, browser/mobile setup, local administrator recovery, storage-preserving rollback, smoke checks and the existing Grafana log troubleshooting path.
- [x] 3.3 Deploy through existing automation limited to Habiki and the applicable component tags; verify valid HTTPS and blocked remote port-3000 access, authorized/unauthorized OIDC, supported mobile sign-in/background backup, API-key/media upload/download including a large upload, realtime access, administrator recovery with Authentik unavailable, log delivery and restart/rebuild persistence. Keep unavailable checks explicitly unverified.
- [x] 3.4 Review the final diff for scope and secrets, validate and archive this OpenSpec change before final commit/PR, and stage only the required files. Close issue #30 only after the required deployed checks pass.
