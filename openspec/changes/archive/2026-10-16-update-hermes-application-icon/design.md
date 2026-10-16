# Decisions

Retain the supplied SVG path, viewBox, transform, fill rule, and explicit
cyan-to-blue gradient. Remove unused CSS classes and add an image role so the
SVG is self-contained and accessible. Render it using the installed KDE SVG
renderer with a 512 × 512 transparent canvas. Keep the existing `hermes.png`
URL to avoid unnecessary OpenTofu or application configuration changes.

# Deployment and Validation

Use the existing Habiki-only `authentik-branding` Ansible deployment tag.
Verify the public PNG returns HTTP 200 and exactly matches the repository asset.
Offline tests cover the standalone SVG structure, gradient, alpha channel,
image dimensions, deployment inclusion, and existing application icon coverage.

# Rollback

Restore the previous PNG from Git and redeploy with the same Ansible command.
