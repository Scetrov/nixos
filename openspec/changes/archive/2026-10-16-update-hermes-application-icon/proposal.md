# Why

Hermes now uses a gradient caduceus SVG rather than the previous raster logo.
The Authentik launcher should reflect its current branding.

# What Changes

- Preserve the operator-supplied SVG as a self-contained source asset.
- Render a transparent 512 × 512 PNG at the existing Hermes icon path.
- Document reproduction and extend offline icon checks.

# Capabilities

## Modified Capabilities

- `authentik-application-icons`: preserve the current Hermes caduceus artwork.

# Impact

Only static branding changes. No application metadata, SSO, access policies,
ports, or service restarts change.
