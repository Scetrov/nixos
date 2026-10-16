# Design

Use a Caddy `route` block to preserve explicit authentication-before-redirect ordering. Caddy ordinarily sorts redirects before `forward_auth`, so relying on textual order without `route` would be unsafe.

After Authentik grants access, handle GET/HEAD `/login` locally. Accept only root-relative ASCII paths containing letters, digits, slashes, underscores and hyphens; reject leading `//` and any `login` path segment. All other targets, including query strings, fragments, encoded paths and dot segments, fall back to `/`. Set `Cache-Control: no-store` and return 302. Other methods continue to Hermes unchanged.

Keep API and health routes unchanged: outpost authentication redirects become same-origin no-store JSON 401, never background cross-origin OAuth fetches. Ordinary unauthenticated browser navigation still reaches Authentik, including requests carrying spoofed identity headers.

This proxy-only fix does not depend on changing Hermes's pinned image. Current upstream source was reviewed for context; it was not treated as proof of the exact deployed image contents. The regression seam exercises the actual repository ingress with pinned Caddy and a simulated Authentik outpost/application.

Rollback: restore the previous `hermes-auth.caddy` through Git and rerun `./scripts/play.sh --limit habiki --tags hermes-auth`. Do not remove Authentik or expose the loopback backend.
