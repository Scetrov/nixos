## 1. Verify the small design works

- [x] 1.1 Check installed service versions and select a compatible released Garage provider under existing dependency policy; use a disposable fixture to prove provider → Authentik → Caddy → Garage authentication through scripts/tofu.sh.
- [x] 1.2 Verify native token scope support, provider key creation/persistence options and false-permission behaviour; record the chosen approach and stop for approval if broader native-token authority is required.
- [x] 1.3 Check existing remote-state transport before adding live credentials; if unprotected, pause for separately agreed remediation rather than expanding this change.

## 2. Add the private management route

- [x] 2.1 Provision the dedicated infrastructure-administration Authentik machine identity/application policy and its Vault-backed credential through existing automation, with bootstrap independent of Garage provider access; use non-interactive machine authentication, not browser/MFA or SSH integration, and never distribute the identity to Minecraft.
- [x] 2.2 Provision the server-side Garage automation token through host-local automation and Vault/agenix; add garage-admin.net.scetrov.live discovery/TLS and the ordered private Caddy authentication/substitution route without changing direct listeners or S3 routes.
- [x] 2.3 Test successful non-interactive machine authorisation, rejected unauthorised tokens/peers and fail-closed Authentik outage; confirm credentials are absent from existing logs and the native Garage token is never returned to clients or retrieved by the wrapper. Operator waived the live Authentik-outage and off-network peer tests as overkill on 2026-10-18. Unauthenticated admin access returned 401, and the proof-window Caddy journal did not contain credential material.

## 3. Provision Minecraft and persist credentials

- [x] 3.1 Extend scripts/tofu.sh minimally for machine-token acquisition and the Garage provider while retaining credential-free local checks and existing secret-output behaviour; supply only the Authentik token to the provider and do not add SSH tunnels or native Garage token retrieval.
- [x] 3.2 Add the minecraft bucket, dedicated key and exact read/list/write binding with bucket deletion protection; check for existing resources before adoption.
- [x] 3.3 Reuse or extend existing helpers to persist the pair atomically in the main Vault without revealing it; test that failed persistence can recover the same pair and preserves unrelated Vault entries.

## 4. Deploy and verify

- [x] 4.1 Run focused wrapper/configuration/permission tests and existing quality gates; deploy the route through targeted Habiki/component automation, then review and apply the Minecraft plan through scripts/tofu.sh.
- [x] 4.2 Confirm Vault persistence, successful upload/read/list, denied cross-bucket access and bucket creation, no extra grants, and a no-change repeat plan; remove only test-owned objects.
- [x] 4.3 Update Garage documentation with client settings, Vault entry names, recovery and non-destructive rollback; explain the accepted cross-bucket management authority, separation from the Minecraft server, the retained approval gate for unscoped native tokens, and the intended Drive-style overwrite/delete semantics without immutable-backup guarantees.
- [x] 4.4 Run configured pre-commit and OpenSpec validation, inspect/stage only intended changes, and archive the completed change before any requested final signed commit/PR.
