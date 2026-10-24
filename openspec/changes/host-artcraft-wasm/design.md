## Context

Habiki already runs Caddy and Authentik's embedded proxy outpost. Caddy configuration lives in `src/roles/nixos/files/etc/nixos/modules/caddy.nix`; Authentik resources and outpost membership are managed in `terraform/`. Existing Ansible branding deployment serves local application icons.

Source inspection found web-packaging entrypoints and official artwork for thirteen editors. Most use Trunk; FilmCraft, LightCraft and EffectCraft have different WASM build paths, and PhotoCraft packages a separate boot stage. These are intended static packages, but no compilation or browser acceptance has yet been performed.

## Goals / Non-Goals

**Goals:**
- Serve thirteen static editor builds under one authenticated hostname on Habiki.
- Provide a correctly branded Authentik tile for every editor.
- Keep build inputs explicit and deployment targeted and repeatable.

**Non-Goals:**
- Application backends, server-side document storage, collaboration, native feature parity, automated upstream discovery/update scheduling, a custom launcher UI, or a generic static-hosting platform.
- Separate access policies for each editor, new runtime containers, databases or network listeners.
- Hosting the Craft Launcher, ArtCraft/ArtCraft-X, empty AniCraft repository, or libraries as applications.

## Decisions

### 1. Existing Caddy serves the static files directly

Use one virtual host, `artcraft.net.scetrov.live`, with thirteen path handlers. The route slugs are `photocraft`, `pdfcraft`, `filmcraft`, `vectorcraft`, `lightcraft`, `designcraft`, `effectcraft`, `gridcraft`, `cadcraft`, `deckcraft`, `soundcraft`, `wordcraft` and `figcraft`.

Authenticate before path stripping or file serving. Canonicalize `/slug` to `/slug/`; only then use relative assets from the upstream packages. Redirect the authenticated site root to `/photocraft/` instead of building a portal. Unknown paths and missing assets return 404; do not introduce a blanket SPA fallback. Disable directory listings. Serve WASM with `application/wasm`, keep entry HTML revalidating and apply long-lived caching only to genuinely content-addressed assets. Translate relevant upstream hosting-header guidance explicitly: Caddy does not consume `_headers` or `.htaccess` files.

Reuse existing TLS, access-log collection and local-networking conventions, adding the alias wherever existing device-host declarations require it. No additional ports are needed.

Alternative rejected: a web-server container per editor or a second static-server process adds runtime components without useful functionality.

### 2. One authorization boundary; thirteen launcher-only tiles

Create one `forward_single` proxy provider for the hostname, attached to a hidden shared ArtCraft application and registered with the existing embedded outpost. Route `/outpost.goauthentik.io/*` to that outpost without recursively applying forward auth. All editor files, including JS, fonts and WASM, remain behind Caddy forward auth. Outpost failure must not expose files.

Bind the shared application to the existing `All Applications` group. Do not grant `General User` access or modify existing memberships. This is a conservative proposal default, not a claim that the operator explicitly selected that group; confirm before applying identity changes.

Create thirteen visible launcher-only applications without individual protocol providers, each with its own name, `/slug/` launch URL, official icon and matching visibility binding. The hidden shared application enforces actual access; tiles are navigation, not independent security boundaries. Verify launcher-only visibility behavior against the installed Authentik version during implementation.

Alternative rejected: thirteen proxy providers on one hostname introduce path-selection ambiguity and unnecessary policy duplication. Shared access was explicitly selected during exploration.

### 3. A small explicit build inventory, not a new build platform

Maintain one checked-in inventory of the thirteen upstream repositories, immutable source revisions with source SHA-256 verification, route slugs and icon provenance. Add build exceptions only where required by upstream packaging. Build in a disposable, unprivileged environment on Habiki, using pinned toolchain/image inputs, no production secrets and no unnecessary host mounts. Build-time containers are allowed; none remain running to serve the applications.

Use upstream `packaging/web/package.sh` contracts after reviewing their reachable build steps. Pin the tool versions they invoke rather than allowing package scripts to install arbitrary latest tools; preserve lockfiles, including matching `wasm-bindgen` CLI/crate versions and pinned Git dependencies. Select applicable released inputs using current upstream evidence and the repository's seven-day non-critical-update policy. Where no suitable release builds, document the exact revision and blocker rather than silently tracking `main`.

Publish complete static outputs, including fonts and PhotoCraft's boot payload, through Ansible to a Caddy-readable location such as `/var/lib/artcraft/<slug>/`. Build and check a candidate before switching that editor's live directory; retain one previous version for rollback. Reuse completed outputs for unchanged pinned inputs. Never build on an HTTP request or replace working output after a failed build.

Alternative rejected: thirteen custom Nix packaging derivations or a dedicated CI service are unnecessary for this initial deployment. Download-only release hosting would not satisfy the requested compilation workflow.

### 4. Reuse local Authentik branding

Take each editor's official artwork from its pinned source, record immutable provenance and SHA-256 checksums, and deploy local PNGs through the existing branding mechanism. OpenTofu owns icon and launch-URL references. Do not substitute generic icons or make launcher images depend on mutable GitHub URLs.

## Risks / Trade-offs

- [A web target does not compile or initialize] → Build every pinned editor and run a browser smoke test; report upstream blockers rather than marking the full suite delivered. Do not expand this change into upstream application development.
- [Native features are unavailable in WASM] → Acceptance is successful editor initialization and basic local interaction, not native parity or working backend integrations.
- [Build scripts execute untrusted dependency code] → Review build entrypoints, isolate builds, verify source integrity and do not expose vault credentials or host control sockets.
- [Large WASM payloads and long builds] → Reuse pinned outputs, preserve upstream packaging and enable existing Caddy compression; no extra caching service.
- [Subpath, font or browser-security requirements differ] → Exercise real assets and browser initialization for each editor; add cross-origin isolation headers only if a verified build needs them and validate login behavior with those headers.
- [All editors share one origin] → Browser storage and same-origin privileges are shared. This matches the requested hostname/path layout and shared access; independent isolation would require a different scope.
- [Stale cached entrypoints or authentication redirects] → Revalidate entry HTML, avoid caching auth responses, and only mark immutable filenames immutable.

## Migration Plan

1. Confirm the access group, resolve pinned inputs and build/check the thirteen candidate packages before enabling the site.
2. Deploy official branding and provision the shared provider, policy, outpost membership and launcher tiles through `scripts/tofu.sh`.
3. Publish static files and deploy the hostname/DNS/Caddy changes through targeted Ansible/NixOS automation (`--limit habiki` and an ArtCraft-specific tag where appropriate).
4. Verify denied and allowed access, all thirteen launch URLs, browser initialization, asset delivery and existing Caddy log ingestion. Run repository validation gates.
5. For a bad editor release, use the same automation to restore its retained directory. To withdraw the suite, remove the virtual host, alias, tiles/provider/outpost membership declaratively without affecting other applications.

## Open Questions

- Confirm `All Applications` as the initial access group before identity changes are applied.
- Exact source/toolchain pins, build resource needs and any browser-specific hosting headers are implementation validation work, not yet established facts.
