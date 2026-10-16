# Why

Forgejo uses Gitea's logo and Miniflux has no configured Authentik icon. Both
need appropriately sized, official application branding.

# What Changes

- Vendor the official Forgejo logo and Miniflux application icon with immutable
  source URLs and SHA-256 provenance.
- Serve both as 512 × 512 PNGs through the existing Authentik branding volume.
- Configure application icons declaratively through OpenTofu.
- Add a narrowly scoped Ansible branding deployment tag and offline tests.

# Capabilities

## New Capabilities

- `authentik-application-icons`: visible applications have appropriate icons;
  Forgejo and Miniflux use locally served, reproducible assets.

# Impact

Two application metadata updates and two additional files in the existing static
branding directory. No authentication policy, membership, port, or service restart
changes. Existing visible application icons remain unchanged.
