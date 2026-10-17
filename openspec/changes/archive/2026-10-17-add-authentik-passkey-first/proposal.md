## Why

Issue [#21](https://github.com/Scetrov/nixos/issues/21) reports username → password → WebAuthn even when an existing passkey could authenticate directly. Enable Authentik's native username-less, passwordless sign-in while preserving existing password/MFA fallback and administrator automation.

## What Changes

- Manage the native candidate authentication flow and its selection through OpenTofu, using `scripts/tofu.sh` for every OpenTofu operation.
- Require user verification for passwordless WebAuthn and avoid redundant password/MFA after trusted native passkey success.
- Pursue native passkey-first prompting with a visible username/password/MFA fallback after cancellation or failure. The operator no longer considers a username-first page with a secondary passkey action and browser-Back fallback sufficient. Investigate native configuration only; no custom CSS or JavaScript.
- Reuse compatible existing passkeys. Preserve credentials, relying-party identity, fallback assurance, application authorization, recovery routing, and the helper's explicit `default-authentication-flow` target.
- Verify the configuration with focused regression checks and the operator's existing passkey/browser combination, then activate with approval and a documented declarative rollback.

## Out of Scope

- Custom UI implementation, Authentik/provider upgrade, new services, ports, routes, or dependencies. Native flow sequencing and a native fallback link may be investigated, but their design and configuration footprint require review before implementation or further live changes.
- Recovery redesign/certification, a new repair identity, or a live token-repair exercise when its routing and behavior are unchanged.
- Certification of every platform authenticator, roaming key, passkey manager, or legacy-credential migration case.
- New enrollment flows unless an actual existing-credential compatibility gap requires one. No forced re-enrollment or credential deletion.
- A comprehensive WebAuthn conformance suite, new test framework, mandatory restart/NixOS rebuild, or production rollback rehearsal.

Existing useful tests may remain, but expanding these areas is not a completion gate. An observed failure affecting the scoped login/fallback behavior remains a blocker.

## Capabilities

### New Capabilities

- `authentik-passkey-authentication`: Native passwordless passkey login with preserved fallback, administrative routing, and reversible deployment.

### Modified Capabilities

None. Application-specific authorization and independent step-up requirements remain unchanged.

## Impact

- `terraform/authentik-flows.tf` and the existing brand selection in `terraform/authentik.tf`.
- Focused tests under `scripts/tests/` and concise operational updates in `docs/authentik.md`.
- Server 2026.8.3 and provider 2026.8.0 were verified during discovery; no upgrade is required by this proposal.
- Production provisioning and activation require separate operator approval. This authorization to edit OpenSpec is not deployment approval.
- Secrets remain vaulted and runtime-injected. See [evidence.md](evidence.md) for historical findings and current verification limits.
