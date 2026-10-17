## Context

GitHub issue #30 concerns Immich on Habiki. Its existing module enables Immich from the existing unstable channel, listens on port 3000 using the service hostname, and opens the firewall. Internal hostname mapping already exists, but Caddy and Authentik integration do not. The operator confirms Immich is unused: no existing-user preservation or migration is required. This does not authorize deleting stored data.

Existing Caddy virtual hosts, Authentik OIDC resources and vault/generated-secret-to-agenix deployment provide the necessary building blocks. No new dependency or shared abstraction is needed.

## Goals / Non-Goals

**Goals:** HTTPS through Caddy, loopback-only application access, native Authentik browser/mobile login, runtime-protected credentials, working application protocols and a simple administrator recovery path.

**Non-Goals:** Existing-user migration, account linking, storage reset, package upgrades/channel changes, automatic SSO redirects, new dashboards, custom authentication middleware or shared-module refactoring.

## Decisions

### Keep the proxy change local to Immich

Set the existing listener to loopback and disable its automatic firewall opening. Define the Caddy virtual host in `immich.nix`, conditional on Immich being enabled, reusing `useACMEHost = "scetrov.live"` and the existing Caddy service. Reuse existing DNS/host mappings; change them only if verification reveals an actual gap.

Use a normal reverse proxy without path rewrites or speculative timeout/upload tuning. Add only settings required by the deployed Immich version's official proxy guidance. This avoids coupling another service to the Grafana guard in the central Caddy module.

### Use native OIDC, not forward authentication

Add one Authentik provider/application in the existing OpenTofu files, with exact version-verified web/mobile redirect URIs and the existing intended-user access policy pattern. Configure Immich's native OAuth/OIDC support and normal first-login provisioning. Do not add group/role mapping unless required for basic access, force automatic login, or introduce a separate Authentik proxy provider: these are unnecessary and risk breaking mobile/API clients.

Keep local password login available for a dedicated administrator recovery account, provisioned through existing automation using the deployed version's supported bootstrap/API/CLI and a runtime-managed credential. Recovery must remain usable when Authentik is unavailable; do not introduce a separate recovery service.

### Reuse runtime secret provisioning

Follow the existing Authentik credential generation/export and Ansible/agenix path; keep vault-managed inputs in the encrypted vault and generated provider credentials in the established generated-secret workflow. Mark relevant OpenTofu outputs sensitive and retain the secured remote backend. Use only `scripts/tofu.sh` for OpenTofu operations.

Prefer the deployed NixOS module's supported secret-file facility. If unavailable, render only the necessary Immich configuration into a permission-restricted runtime file from agenix credentials and point Immich at it. Do not put secret values into Nix settings, derivations, command arguments, logs or source control. Extend existing deployment ordering/validation only as needed so missing or stale credentials cannot silently reach Immich; do not build a new orchestration framework.

## Risks / Trade-offs

- [The unstable package and service module may expose different configuration options] → Inspect the actual installed/evaluated version and upstream documentation before selecting options or redirect URIs; do not upgrade as part of this work.
- [A runtime OIDC secret exists in OpenTofu state] → Keep existing protected remote state, sensitive outputs and redacted verification; never print credentials.
- [Native OIDC works in browsers but fails on mobile] → Verify the supported mobile callback and real backup flow; avoid a proxy-auth gate.
- [Retaining local login adds a second authentication path] → Restrict it operationally to a strong, securely stored administrator recovery credential; test recovery with Authentik unavailable.
- [Proxying changes media transport behaviour] → Exercise uploads, background sync and realtime access using existing tools/clients rather than creating a new test platform.

## Migration Plan

1. Verify the deployed version/options, listener, certificate coverage, intended Authentik access group and existing secret deployment sequence.
2. Provision the provider/application via the secure wrapper, then deliver matching runtime credentials before enabling OIDC consumer configuration.
3. Deploy only to Habiki through existing targeted automation; preserve database and media storage. Establish and test administrator recovery before relying on OIDC.
4. Verify HTTPS, browser/mobile OIDC, API access, uploads, sync, realtime behaviour, rejection of direct port-3000 access, and persistence after restart/rebuild. Confirm existing journal/log collection still delivers relevant failures to Grafana; no new dashboard or alerting system.
5. Roll back OIDC settings/provider changes through automation if necessary, retaining local administrator login and the Caddy/loopback boundary. Do not reopen port 3000 as an authentication workaround or reset storage.

## Verified integration choices (2026-10-17)

- Habiki reports Immich **3.3.1** through `/api/server/version`; its active service executes `/nix/store/zwn80jl9fnxdmzpnbfxm8v6sy09pbfq7-immich-3.3.1/bin/server`. Keep the existing package/channel selection unchanged. The listener currently binds `10.229.10.2:3000`.
- The installed NixOS module supports `services.immich.settings.oauth.clientId._secret` and `clientSecret._secret`, using `LoadCredential` and `utils.genJqSecretsReplacement` to render `/run/immich/config.json` before startup. Use that native facility with root-readable agenix files; no custom configuration renderer.
- Version-tagged [OAuth guidance](https://github.com/immich-app/immich/blob/v3.3.1/docs/docs/administration/oauth.md) specifies strict callbacks `https://immich.net.scetrov.live/auth/login`, `https://immich.net.scetrov.live/user-settings` and `app.immich:///oauth-callback`. Keep auto-registration enabled and auto-launch disabled.
- Version-tagged [reverse-proxy guidance](https://github.com/immich-app/immich/blob/v3.3.1/docs/docs/administration/reverse-proxy.md) supports a plain Caddy `reverse_proxy`, without a subpath or upload-size limit. Preserve Host and forwarded headers; explicitly supply X-Real-IP. Caddy handles websocket upgrades natively.
- The deployed CLI supports password reset but not first-administrator creation. Use the native `POST /api/auth/admin-sign-up` bootstrap API (email/name/password body), then verify local login/admin status; never reset an initialized database or silently replace an existing administrator. Keep `passwordLogin.enabled = true`. See the [version-tagged auth controller](https://github.com/immich-app/immich/blob/v3.3.1/server/src/controllers/auth.controller.ts).
- Operator confirmed reuse of **All Applications** (currently scetrov only), excluding General User. Operator authorized a dedicated recovery identity `git@scetrov.live` and generation of a strong password in encrypted `src/secrets.yml`; deliver both through agenix, never chat, command arguments or logs.

## Open Questions

- Habiki resolves the existing Immich alias to `10.229.10.2`. The live trusted certificate served by the existing Caddy identity host includes `*.net.scetrov.live` (expires 2026-12-31), covering Immich; no DNS or certificate changes are required.
- Existing ordering is OpenTofu provider/app/group binding apply → encrypted generated outputs → Ansible vars_files → protected agenix generation/copy → NixOS rebuild. Add a Habiki-only `immich` tag following the Miniflux workflow: provision only Immich's binding dependency graph before loading variables, prohibit stale-output bypass, and skip channel updates/blanket container restarts.

## Deployment and verification evidence (2026-10-17)

- `scripts/play.sh --limit habiki --tags immich` succeeded: OpenTofu added five Immich resources with zero changed/destroyed resources; Ansible finished `ok=69 changed=15 failed=0 unreachable=0`. Channel updates, blanket container restarts and Frontier transition tasks were skipped.
- Verified trusted HTTPS on the Immich hostname, unchanged server version 3.3.1, OIDC enabled, password login enabled, auto-launch disabled and initialized administrator state. A connection to Habiki port 3000 from the agent host timed out; Habiki's listener is only `127.0.0.1:3000`.
- Runtime configuration is mode 0600; all four agenix inputs are mode 0400. Runtime OIDC client ID/secret match their protected input files (boolean-only verification; no credential contents printed).
- Initial startup logged local administrator recovery verification. A subsequent service restart through targeted Ansible succeeded; web and mobile authorization-initiation calls still discover Authentik and return the exact configured callbacks. These are initiation checks, **not completed OIDC logins**.
- Grafana's Loki datasource query returned status 200 and the unique recovery-verification journal event, proving existing log delivery.
- Validation passed: 12 generated-secret tests, 13 Immich regression/bootstrap/Vault tests, six existing Miniflux identity tests, secret-free evaluated Nix assertions (version 3.3.1), wrapper-based OpenTofu validation/format checks, targeted Ansible syntax check, and all configured pre-commit gates (including redacted gitleaks). New untracked files were also checked explicitly.
- **Initially unverified by the agent; subsequently completed by the operator:** complete authorized/unauthorized browser OIDC sign-in; real mobile sign-in/background backup; API-key media upload/download and representative large upload; authenticated realtime connection; local administrator recovery with Authentik actually unavailable; stored-media and user-session persistence across a subsequent rebuild. A successful initial rebuild/restart and API discovery do not substitute for those checks.

At the initial pause, task 3.3 remained incomplete pending these client/operational checks. After initially reporting that the service worked operationally, the operator explicitly confirmed: "Completed operator client verification. Please archive, commit and push." Task 3.3 is complete on the basis of that operator confirmation. These client-check results are operator-attested, not additional agent-executed evidence.

### Follow-up: Authentik launcher icon

The operator requested an Immich application icon. Reused Immich's official 512 × 512 favicon from immutable commit `db6e11ecc851228aec9c525abb0ee026d1f5055e` (release 3.3.1), stored locally with SHA-256 `a4cda3df8fe52ccf11431cf691ebbfcbc3694d4d8b4d922d6ae43fedf25c43ff`. Added it to the existing Ansible branding copy list and set the application's `meta_icon` to `/static/dist/branding/immich-a4cda3df8fe5.png`. The asset-only Habiki deployment and wrapper-based application-only OpenTofu apply succeeded (zero added/destroyed, one application updated); no rebuild or restart. Authentik's API returns the expected icon path, and the HTTPS-served PNG matches its recorded checksum. All 14 Immich tests pass, including icon provenance/deployment checks.
