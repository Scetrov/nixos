## Why

Make the Craft editor suite available privately in a browser on Habiki without operating application backends. Use upstream's published WASM release bundles with existing Caddy and Authentik infrastructure; local compilation is unnecessary.

## What Changes

- Download, verify and publish official GitHub WASM release bundles for thirteen Storytold editors: PhotoCraft, PdfCraft, FilmCraft, VectorCraft, LightCraft, DesignCraft, EffectCraft, GridCraft, CADCraft, DeckCraft, SoundCraft, WordCraft and FigCraft.
- Serve each editor at its lowercase repository-name path under `https://artcraft.net.scetrov.live/`, with a trailing slash.
- Protect the entire site with one existing-outpost Authentik proxy-auth integration and a shared access policy, initially bound to the existing `All Applications` group.
- Create thirteen Authentik launcher applications with individual launch URLs and official, locally served icons.
- Automate version- and SHA-256-pinned release downloads, targeted publication, DNS and Caddy configuration using existing repository conventions. Keep the currently published files when a download, integrity check or package validation fails.
- Exclude AniCraft (currently empty), the Craft Launcher, supporting libraries as standalone sites, ArtCraft/ArtCraft-X platforms, backends, collaboration services and per-editor access policies. No source compilation, build containers, Rust/WASM toolchain installation, new runtime containers, databases or listening ports.

## Capabilities

### New Capabilities

- `artcraft-static-suite`: Reproducible static WASM publication, path-based hosting, shared authentication and application launcher entries for the thirteen editors.

### Modified Capabilities

None. Existing Authentik application-icon requirements continue to apply without modification.

## Impact

- NixOS Caddy and local-networking configuration on Habiki and the existing device-host DNS declarations.
- Ansible download/publication orchestration and existing Authentik branding deployment.
- OpenTofu Authentik provider, application, policy binding and embedded-outpost declarations, operated only through `scripts/tofu.sh`.
- Pinned upstream release archives; no build-toolchain dependencies or new application runtime service. Replace the in-flight compilation flow with downloads, retaining useful package-validation and publication safeguards.
- Focused configuration checks, release-bundle validation and authenticated browser smoke tests. Bundle availability, completeness and browser behavior must be verified for every editor.
