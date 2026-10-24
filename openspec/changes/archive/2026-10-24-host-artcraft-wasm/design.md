## Context

Habiki already runs Caddy and Authentik's embedded proxy outpost. Caddy configuration lives in `src/roles/nixos/files/etc/nixos/modules/caddy.nix`; Authentik resources and outpost membership are managed in `terraform/`. Existing Ansible branding deployment serves local application icons.

The operator confirmed that this change should consume published GitHub WASM bundles, not compile source. The earlier compilation requirement was unnecessary and is superseded. Verify the availability and completeness of each editor's official release bundle during implementation; browser acceptance remains outstanding.

## Goals / Non-Goals

**Goals:**
- Serve thirteen official static WASM release bundles under one authenticated hostname on Habiki.
- Provide a correctly branded Authentik tile for every editor.
- Keep release versions, asset URLs and SHA-256 checksums explicit, with targeted and repeatable deployment.

**Non-Goals:**
- Application backends, server-side document storage, collaboration, native feature parity, automated upstream discovery/update scheduling, a custom launcher UI, or a generic static-hosting platform.
- Source compilation, build containers, Rust/WASM toolchain installation, separate access policies for each editor, new runtime containers, databases or network listeners.
- Hosting the Craft Launcher, ArtCraft/ArtCraft-X, empty AniCraft repository, or libraries as applications.

## Decisions

### 1. Existing Caddy serves the static files directly

Use one virtual host, `artcraft.net.scetrov.live`, with thirteen path handlers. The route slugs are `photocraft`, `pdfcraft`, `filmcraft`, `vectorcraft`, `lightcraft`, `designcraft`, `effectcraft`, `gridcraft`, `cadcraft`, `deckcraft`, `soundcraft`, `wordcraft` and `figcraft`.

Authenticate before path stripping or file serving. Canonicalize `/slug` to `/slug/`; only then use relative assets from the upstream packages. Redirect the authenticated site root to `/photocraft/` instead of building a portal. Unknown paths and missing assets return 404; do not introduce a blanket SPA fallback. Disable directory listings. Serve WASM with `application/wasm`, keep entry HTML revalidating and apply long-lived caching only to genuinely content-addressed assets. Translate relevant upstream hosting-header guidance explicitly: Caddy does not consume `_headers` or `.htaccess` files.

Reuse existing TLS, access-log collection and local-networking conventions, adding the alias wherever existing device-host declarations require it. No additional ports are needed.

Alternative rejected: a web-server container per editor or a second static-server process adds runtime components without useful functionality.

### 2. One authorization boundary; thirteen launcher-only tiles

Create one `forward_single` proxy provider for the hostname, attached to a hidden shared ArtCraft application and registered with the existing embedded outpost. Route `/outpost.goauthentik.io/*` to that outpost without recursively applying forward auth. All editor files, including JS, fonts and WASM, remain behind Caddy forward auth. Outpost failure must not expose files.

Bind the shared application to the existing `All Applications` group. Do not grant `General User` access or modify existing memberships. The operator explicitly confirmed `All Applications` during implementation on 2026-10-24; use it for both authorization and tile visibility.

Create thirteen visible launcher-only applications without individual protocol providers, each with its own name, `/slug/` launch URL, official icon and matching visibility binding. The hidden shared application enforces actual access; tiles are navigation, not independent security boundaries. Verify launcher-only visibility behavior against the installed Authentik version during implementation.

Alternative rejected: thirteen proxy providers on one hostname introduce path-selection ambiguity and unnecessary policy duplication. Shared access was explicitly selected during exploration.

### 3. Download official release bundles; do not compile source

Maintain one small checked-in inventory with each editor's release version, explicit official GitHub release-asset URL/filename, expected SHA-256, route slug and icon provenance. Choose the newest applicable stable release outside the repository's seven-day non-critical-update holdback, checking current upstream release metadata. Do not use mutable `latest` download URLs. Verify downloaded bytes against the checked-in checksum before extraction; a replaced asset with the same filename must fail verification.

Use targeted Ansible download and extraction tasks. Treat archives as data: do not execute upstream packaging/install scripts, install Rust/WASM tooling or start build containers. Check archives for unsafe paths and links before extracting into a candidate directory, and validate the entry HTML, WASM and required runtime assets at the intended path prefix. Consume the complete bundle, including fonts and any boot payload it requires. If no suitable official bundle exists or a bundle is incomplete, report the affected editor and blocker; do not silently omit it, compile a substitute or introduce backend services.

Publish the checked candidate to a Caddy-readable location such as `/var/lib/artcraft/<slug>/` only after download, checksum and package checks succeed. Switch the live publication atomically, retain one previous working version for rollback, and reuse verified unchanged downloads/publications. A failed download or candidate check must leave currently served files intact. Existing package-validation and atomic-publication helpers/tests may be reused; replace the compilation path and remove its now-unused builder files, toolchain pins and build-only tests rather than maintaining two delivery modes.

Alternative rejected: compiling upstream sources on Habiki adds toolchain dependencies, container setup, host resource load and failure modes without being necessary to serve published WASM bundles. No local compilation fallback is in scope.

### 4. Reuse local Authentik branding

Take each editor's official artwork from its pinned source, record immutable provenance and SHA-256 checksums, and deploy local PNGs through the existing branding mechanism. OpenTofu owns icon and launch-URL references. Do not substitute generic icons or make launcher images depend on mutable GitHub URLs.

## Risks / Trade-offs

- [A release has no usable WASM bundle or does not initialize] → Verify all thirteen official bundles and run browser smoke tests; report upstream packaging blockers rather than claiming the suite is delivered or compiling replacements.
- [Native features are unavailable in WASM] → Acceptance is successful editor initialization and basic local interaction, not native parity or working backend integrations.
- [A release asset is replaced or contains unsafe archive entries] → Pin and verify its SHA-256 before safe extraction; execute no package scripts and preserve the live publication on failure.
- [Large WASM payloads] → Reuse verified downloads, preserve complete runtime assets and enable existing Caddy compression; no extra caching service.
- [Subpath, font or browser-security requirements differ] → Exercise real assets and browser initialization for each editor; add cross-origin isolation headers only if a verified bundle needs them and validate login behavior with those headers.
- [All editors share one origin] → Browser storage and same-origin privileges are shared. This matches the requested hostname/path layout and shared access; independent isolation would require a different scope.
- [Stale cached entrypoints or authentication redirects] → Revalidate entry HTML, avoid caching auth responses, and only mark immutable filenames immutable.

## Migration Plan

1. Retain the confirmed access group, replace the in-flight build flow with pinned release downloads, and download/check all thirteen candidate bundles before enabling the site.
2. Deploy official branding and provision the shared provider, policy, outpost membership and launcher tiles through `scripts/tofu.sh`.
3. Publish static files and deploy the hostname/DNS/Caddy changes through targeted Ansible/NixOS automation (`--limit habiki` and an ArtCraft-specific tag where appropriate).
4. Verify denied and allowed access, all thirteen launch URLs, browser initialization, asset delivery and existing Caddy log ingestion. Run repository validation gates.
5. For a bad editor release, use the same automation to restore its retained directory. To withdraw the suite, remove the virtual host, alias, tiles/provider/outpost membership declaratively without affecting other applications.

## Open Questions

- Resolved 2026-10-24: the operator confirmed `All Applications` as the initial access group.
- Exact release-asset URLs/checksums, complete runtime-asset availability and any browser-specific hosting headers remain implementation validation work. Earlier source/toolchain pins do not establish release-bundle integrity.
