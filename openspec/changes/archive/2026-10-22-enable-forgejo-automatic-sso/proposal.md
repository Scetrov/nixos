## Why

Issue #23 describes an unnecessary second login click even though Forgejo already uses native Authentik OIDC. Automatically entering that existing flow makes browser access seamless without weakening native Git/API authentication or private access boundaries.

## What Changes

- Automatically initiate Authentik OIDC for unauthenticated interactive browser access using a supported mechanism verified against the installed Forgejo version.
- Preserve existing sessions, supported deep links, OIDC validation, failure/logout handling, and secure administrative recovery.
- Add focused configuration and browser acceptance coverage without introducing blanket proxy authentication.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `forgejo-authentik-access`: Add automatic interactive OIDC entry with explicit callback, logout, recovery, and non-browser compatibility requirements.

## Impact

Issue #23; Forgejo NixOS configuration and existing identity reconciliation, relevant tests, and `docs/forgejo.md`. Caddy or Authentik changes only if the supported mechanism demonstrably requires them; identity changes use the OpenTofu wrapper. No Dependency-Track changes, runner activation, new public endpoints, or custom authentication framework.
