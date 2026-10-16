## Context

Unauthenticated live `/api/projects` returns 302 to Authentik. The deployed Hermes WebUI already implements `_redirectIfUnauth` and API-level 401 recovery. Caddy forward_auth currently forwards the outpost's redirect before Hermes sees the request.

## Goals / Non-Goals

**Goals:** Keep background failures same-origin; retain top-level login redirects and fail-closed access controls; deploy via targeted Ansible/NixOS automation.

**Non-Goals:** Relaxing CSP/CORS, extending session lifetimes, upgrading or patching the WebUI image, or changing other virtual hosts.

## Decisions

1. Use exclusive Caddy handles for `/api`, `/api/*`, `/health`, and `/health/*`, and a browser fallback. Only background outpost 3xx responses become JSON 401 with Cache-Control no-store and no Location. Existing 401/403/5xx remain failures, never bypasses.
2. Keep the Caddy body in a readFile fragment so the container fixture exercises exactly the production rules. Successful auth continues through the same reverse proxy with the existing identity headers and unconsumed request body.
3. Use the frontend's existing 401 login navigation rather than a brittle injected script. Verify that behavior against deployed JavaScript. SSE handshake failures are 401; normal background polling triggers navigation.
4. Use the repository-pinned Caddy container image with mocked auth and app upstreams, no production credentials, and only localhost published ports. Also run sandboxed frontend tests and live no-cookie probes.

## Risks / Trade-offs

- Existing open streams are not forcibly revoked by this change; reconnects and polling reauthenticate as before.
- Clients already holding old pages require no new script, but upstream future changes could alter 401 recovery. Keep a runtime handler check in the operational verification.
- NixOS rebuild affects a shared host: use the focused `hermes-auth` play (only two module files; no channel refresh or blanket container restarts), restrict to Habiki, inspect module drift, and verify Caddy and Hermes afterwards. Roll back by reverting the fragment/config and redeploying.
