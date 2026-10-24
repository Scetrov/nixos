## Why

Make the Craft editor suite available privately in a browser on Habiki without operating application backends. Upstream already provides WASM web-packaging entrypoints, so existing Caddy and Authentik infrastructure should be sufficient.

## What Changes

- Build and publish static WASM packages for thirteen Storytold editors: PhotoCraft, PdfCraft, FilmCraft, VectorCraft, LightCraft, DesignCraft, EffectCraft, GridCraft, CADCraft, DeckCraft, SoundCraft, WordCraft and FigCraft.
- Serve each editor at its lowercase repository-name path under `https://artcraft.net.scetrov.live/`, with a trailing slash.
- Protect the entire site with one existing-outpost Authentik proxy-auth integration and a shared access policy, initially bound to the existing `All Applications` group.
- Create thirteen Authentik launcher applications with individual launch URLs and official, locally served icons.
- Automate pinned builds, targeted publication, DNS and Caddy configuration using existing repository conventions. Keep the currently published files when a build fails.
- Exclude AniCraft (currently empty), the Craft Launcher, supporting libraries as standalone sites, ArtCraft/ArtCraft-X platforms, backends, collaboration services and per-editor access policies. No new runtime containers, databases or listening ports.

## Capabilities

### New Capabilities

- `artcraft-static-suite`: Reproducible static WASM publication, path-based hosting, shared authentication and application launcher entries for the thirteen editors.

### Modified Capabilities

None. Existing Authentik application-icon requirements continue to apply without modification.

## Impact

- NixOS Caddy and local-networking configuration on Habiki and the existing device-host DNS declarations.
- Ansible build/publication orchestration and existing Authentik branding deployment.
- OpenTofu Authentik provider, application, policy binding and embedded-outpost declarations, operated only through `scripts/tofu.sh`.
- Build-time Rust/WASM tooling and upstream source dependencies; no new application runtime service.
- Focused configuration checks, real WASM builds and authenticated browser smoke tests. Buildability and browser feature parity have not yet been established for every editor.
