# Skip Hermes native login after Authentik recovery

## Why

Hermes's API 401 handler navigates to `/login?next=…`. Disabling its native password did not remove that route, leaving an unnecessary Login click after Authentik session recovery.

## What Changes

- Authenticate browser navigation with Authentik before handling Hermes login recovery.
- Redirect authenticated GET/HEAD `/login` requests directly to a conservative local return path, otherwise `/`.
- Prevent caching of recovery redirects and preserve background API 401 behavior.

## Capabilities

### Modified Capabilities

- `hermes-session-expiry`: resume sessions without the native login page after Authentik grants access.

## Impact

Only the Hermes Caddy ingress rules, their regression fixture, and the existing expiry specification change. No Hermes image, secret, identity policy, or exposed port changes.
