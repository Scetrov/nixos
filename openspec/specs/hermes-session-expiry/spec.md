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
The ingress SHALL preserve ordinary browser authentication redirects and the WebUI SHALL navigate at top level on API 401 using its existing login recovery. In this proxy-only deployment, after successful Authentik authentication, GET and HEAD requests to `/login` SHALL redirect to a validated local return path without rendering Hermes's native login page. The ingress SHALL execute authentication before login recovery and SHALL mark recovery redirects `Cache-Control: no-store`.

#### Scenario: Expired browser navigation
- **WHEN** an unauthenticated browser visits `/` or `/login`
- **THEN** the normal Authentik redirect is retained

#### Scenario: Frontend receives an expired-session response
- **WHEN** the existing WebUI authentication handler receives HTTP 401
- **THEN** it navigates to the same-origin login route with the current page as the return target, without weakening CSP

#### Scenario: Authenticated login recovery resumes the session
- **WHEN** Authentik grants access to `/login?next=%2Fsession%2Fexample`
- **THEN** Caddy returns a non-cacheable 302 to `/session/example` instead of reaching Hermes's native login page

#### Scenario: Unsafe or unsupported return target
- **WHEN** an authenticated login recovery request has no return target or a target outside simple root-relative paths containing only ASCII letters, digits, slashes, underscores and hyphens, or starts with `//`, or contains a `login` path segment
- **THEN** Caddy returns a non-cacheable 302 to `/`, rejecting external URLs, backslashes, control characters, nested encoding, dot segments and login loops
- **AND** query strings and fragments in return targets deliberately fall back to `/`

#### Scenario: Login recovery is not an authentication bypass
- **WHEN** Authentik denies or fails a login recovery request, including a request carrying a spoofed identity header
- **THEN** Caddy retains Authentik's redirect or denial and does not redirect to the requested Hermes return target

#### Scenario: Non-navigation methods are preserved
- **WHEN** an Authentik-authenticated client sends POST to `/login`
- **THEN** the request reaches Hermes unchanged rather than receiving the GET/HEAD recovery redirect
