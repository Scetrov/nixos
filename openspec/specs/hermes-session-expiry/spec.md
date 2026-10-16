# hermes-session-expiry Specification

## Purpose

Keep Hermes background requests same-origin when Authentik sessions expire, and recover through top-level browser reauthentication without weakening CSP or access controls.

## Requirements
### Requirement: Background authentication expiry stays same-origin
The Hermes ingress SHALL convert authentication redirects for `/api`, `/api/*`, `/health`, and `/health/*` into non-cacheable JSON HTTP 401 without a Location header, while requiring successful authentication before accessing Hermes.

#### Scenario: Expired polling or stream handshake
- **WHEN** the outpost returns an OAuth redirect for a background request
- **THEN** the client receives 401 without contacting the identity origin and the application upstream is not called

#### Scenario: Authenticated request
- **WHEN** the outpost grants access
- **THEN** the original method, body, path, query, and identity headers reach Hermes

#### Scenario: Authentication backend fails
- **WHEN** the outpost returns 403 or 5xx
- **THEN** access remains denied without reaching Hermes

### Requirement: Browser reauthentication remains available
The ingress SHALL preserve ordinary browser authentication redirects and the WebUI SHALL navigate at top level on API 401 using its existing login recovery.

#### Scenario: Expired browser navigation
- **WHEN** an unauthenticated browser visits `/` or `/login`
- **THEN** the normal Authentik redirect is retained

#### Scenario: Frontend receives an expired-session response
- **WHEN** the existing WebUI authentication handler receives HTTP 401
- **THEN** it navigates to the same-origin login route with the current page as the return target, without weakening CSP
