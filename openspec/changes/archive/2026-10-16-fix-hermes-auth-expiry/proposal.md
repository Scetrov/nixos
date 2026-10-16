## Why

Issue #32: expired Authentik sessions redirect Hermes background requests to the identity origin, which CSP blocks before the frontend can handle authentication expiry.

## What Changes

- Return non-cacheable JSON 401 responses instead of OAuth redirects for Hermes API and health requests.
- Preserve browser navigation redirects, Authentik authorisation, and the existing CSP.
- Exercise the actual Caddy configuration in a pinned-container regression fixture and verify the deployed frontend's existing login redirect handler.

## Capabilities

### New Capabilities
- `hermes-session-expiry`: Safe background authentication failure and browser reauthentication.

### Modified Capabilities
None.

## Impact

Hermes host Caddy configuration, regression tests, and operational documentation. No image upgrades, secrets, provider lifetime changes, or new exposed routes.
