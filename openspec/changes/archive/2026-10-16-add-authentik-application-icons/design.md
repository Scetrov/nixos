# Context

Ansible copies branding into `/var/lib/authentik/branding`, already mounted by
Authentik at `/web/dist/branding`. OpenTofu owns application metadata. Four other
visible applications already have appropriate icons; Metrics and the duplicate
Home Assistant OIDC application are intentionally hidden.

# Decisions

- Use official upstream artwork, not a third-party icon catalogue or Gitea logo.
- Render Forgejo's vector logo at 512 × 512 with transparency using the installed
  KDE SVG renderer. Retain its unmodified SVG source for reproducibility.
- Use Miniflux's upstream 512 × 512 PNG unchanged, avoiding a new image dependency.
- Record immutable upstream commits and source hashes beside the assets.
- Add `authentik-branding` to the existing asset-copy task so a targeted deployment
  does not rebuild the host, restart services, or reconcile unrelated resources.
- Apply only the two application resources using the mandatory secure wrapper.

# Validation

Offline tests check visible-app icon coverage, local references, deployment loop,
PNG dimensions, and source hashes. Live verification uses the Authentik application
API with `superuser_full_list=true` (the default list excludes apps unavailable
to the automation user), then fetches every visible application's icon.

# Rollback

Revert the application metadata through OpenTofu. Unreferenced PNGs may be removed
through automation if desired; they expose no additional route or port.
