## Why

A future project needs an S3-compatible destination for its backups without exposing backup data to the public internet. Habiki is always on and has a 4 TB SSD, making it an appropriate private object-storage target for one shared tailnet.

## What Changes

- Add a persistent S3-compatible object-storage service on Habiki, initially using Garage.
- Make the S3 API and administrative interface reachable only from the Headscale tailnet and local Habiki management paths.
- Provide encrypted-secret-backed administrative and per-project access credentials, with least-privilege bucket access and no anonymous access.
- Reserve persistent host storage and monitor service availability and capacity through the existing observability stack.
- Define a reusable bucket and credential provisioning pattern without backing up or migrating existing repository-managed services.

## Capabilities

### New Capabilities
- `tailnet-s3-backup-target`: A private, persistent S3-compatible backup destination on Habiki.

### Modified Capabilities

None.

## Impact

- Affected NixOS host configuration: Habiki device configuration and a new object-storage module.
- Affected secrets: Garage administrative credentials and project access credentials supplied through agenix/Ansible Vault workflows.
- New runtime dependency: Garage and its supported persistent-data configuration.
- Affected network policy: service listeners and firewall rules limited to the Headscale tailnet; no WAN router forwarding or public Caddy route.
- New observability surface: object-storage availability, storage capacity, and supported service metrics.
