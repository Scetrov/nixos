# Authentik application icons

Application icons are served locally from `/static/dist/branding/`. Ansible
copies the assets into the existing Authentik branding volume; OpenTofu owns
application `meta_icon` references. No new endpoints or ports are needed.

## Forgejo and Miniflux

Both icons use a 512 × 512 pixel canvas. Forgejo is rendered on a transparent
background; Miniflux uses its upstream black-on-white application icon.

| Asset | Immutable upstream source | Source SHA-256 |
| --- | --- | --- |
| `sources/forgejo.svg` | <https://codeberg.org/forgejo/forgejo/raw/commit/acd7bc15db65b7a4b9a216b3e1a8772fe7d4d128/assets/logo.svg> | `acfeda65446d1c17c5d8e62e18b70a6616ef20df81e7de93ff791a3b11d4be28` |
| `miniflux.png` | <https://raw.githubusercontent.com/miniflux/v2/c317f84bc3779bc5d936b75408b631589983c81a/internal/ui/static/bin/icon-512.png> | `5fcba35404ffcd8994d615df09653c00812f2b4d6539eb511df4f9e3cd4f8c5a` |

Forgejo identifies `assets/logo.svg` as its logo in its
[customization documentation](https://forgejo.org/docs/latest/contributor/customization/).
The Miniflux icon is the official application's 512-pixel icon, copied unchanged.
These logos remain the property of their respective projects.

To reproduce Forgejo's PNG with KDE's SVG renderer (use absolute file paths):

```sh
QT_QPA_PLATFORM=offscreen ksvgtopng 512 512 /absolute/path/sources/forgejo.svg /absolute/path/forgejo.png
```

Deploy assets without rebuilding NixOS or restarting Authentik:

```sh
./scripts/play.sh --limit habiki --tags authentik-branding --skip-generated-refresh
```

Then review and apply only the application metadata through the secure wrapper:

```sh
./scripts/tofu.sh -- plan -target=authentik_application.forgejo -target=authentik_application.miniflux
./scripts/tofu.sh -- apply -target=authentik_application.forgejo -target=authentik_application.miniflux
```

Check the saved application icons through the Authentik API using
`/api/v3/core/applications/?superuser_full_list=true&page_size=100` with the
vault-backed automation credential, and fetch each visible application's icon
URL. The default list only includes applications accessible to the caller. Metrics and Home Assistant's duplicate OIDC
application are intentionally hidden; existing visible applications retain their
configured Grafana, Hermes, Dependency Track, and Home Assistant icons.
