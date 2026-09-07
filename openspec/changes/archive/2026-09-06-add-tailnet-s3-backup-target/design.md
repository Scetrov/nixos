## Context

Habiki is the always-on infrastructure host and has a 4 TB SSD. A future project requires an S3-compatible backup destination, but existing repository-managed services are not being migrated and Habiki itself is intentionally treated as reproducible rather than as a disaster-recovery target.

The companion Headscale change establishes a single private tailnet. This storage service must be useful from that tailnet without adding a WAN port-forward, public Caddy route, or router-specific VPN dependency.

## Goals / Non-Goals

**Goals:**
- Provide a persistent, S3-compatible API suitable for backup clients on the shared tailnet.
- Keep data-plane and management access private to the tailnet and Habiki-local administration.
- Keep secrets out of Nix expressions and version control.
- Provide a secure, repeatable pattern for project buckets and scoped credentials.
- Make availability, capacity, and supported storage metrics observable.

**Non-Goals:**
- Off-host replication, high availability, or a multi-node object-storage cluster.
- Backup or migration of current repository-managed services.
- Public S3 access, public bucket hosting, or WAN router forwarding.
- Providing S3 Object Lock/immutable retention in the initial release.
- Automatically provisioning a future project's buckets before that project and its access needs are known.

## Decisions

### Use Garage as the initial single-node S3 service

Garage SHALL be the initial S3-compatible service because it is maintained, packaged in the pinned NixOS release, and supports a single-node deployment with a familiar S3 API. The final MinIO OSS release is marked insecure by Nixpkgs for unauthenticated-write CVEs and SHALL NOT be used. Garage data and service configuration SHALL be persistent on Habiki's host storage.

**Alternatives considered:** MinIO AIStor requires a separately licensed/vendor-distributed package. Cloud S3 would provide off-host durability but does not meet the self-hosted local-target objective.

### Store Garage state beneath `/var/lib/garage`

The single-node instance SHALL store object data in `/var/lib/garage/data` and metadata in `/var/lib/garage/meta` on Habiki's persistent SSD-backed root filesystem. The NixOS Garage module's dynamic service account SHALL be the only service identity permitted to access these directories; runtime credentials and certificate keys SHALL remain separately injected secrets with mode `0400`. This keeps service state persistent while preventing non-service users from reading backup data.

### Treat the service as a private tailnet endpoint

The S3 API SHALL bind only to Habiki's Headscale tailnet address (and any required local loopback management path). Firewall policy SHALL permit it only on the tailnet interface/address. No WAN listener, router port-forward, or public Caddy virtual host SHALL be created for the API or console.

**Alternatives considered:** A public endpoint increases credential-attack surface and is unnecessary for tailnet-connected backup clients. LAN-wide binding permits unintended local clients and weakens the intended boundary.

### Use HTTPS with tailnet DNS

Backup clients SHALL use an HTTPS S3 endpoint. The implementation SHALL provide a trusted certificate for a dedicated service hostname and ensure that tailnet clients resolve that hostname to Habiki's tailnet address, without publishing a public S3 route. The certificate and private key SHALL be supplied through the existing encrypted secret workflow.

**Alternatives considered:** Plain HTTP inside WireGuard is encrypted in transit but exposes credentials to accidental non-tailnet routing/configuration and is less compatible with secure client defaults. Per-client self-signed certificate exceptions do not scale safely.

### Separate administrative and project credentials

Garage administrative credentials and project access credentials SHALL be distinct. Credentials SHALL be supplied at runtime through agenix/Ansible Vault workflows, never hardcoded in Nix or OpenSpec artifacts. Each future project SHALL receive an isolated bucket and a least-privilege policy limited to that bucket.

**Alternatives considered:** A shared administrator credential makes routine backup clients overly powerful. Anonymous buckets are incompatible with backup data confidentiality.

### Capacity monitoring without implied disaster recovery

The service SHALL emit availability and supported storage/capacity metrics to the existing monitoring stack. Capacity alert thresholds SHALL reserve room for recovery operations. The design intentionally does not claim resilience against Habiki or SSD loss.

**Alternatives considered:** Multi-drive erasure coding can tolerate drive failures but cannot recover loss of Habiki and requires a storage layout not currently defined in this repository.

## Risks / Trade-offs

- [The 4 TB SSD is a single point of failure] → this is an accepted constraint; document the target as local backup infrastructure rather than disaster recovery.
- [Backup data fills shared host storage] → persist data in a dedicated path, collect capacity metrics, and alert before the agreed reserve threshold is exhausted.
- [A future client lacks tailnet DNS/certificate trust] → validate an end-to-end backup-client configuration before relying on the target; keep endpoint and trust distribution in the project integration plan.
- [Administrative credentials leak] → use encrypted runtime secret injection, distinct project credentials, least-privilege policies, and revocation/rotation procedures.
- [Garage or NixOS module behavior changes] → verify the current supported package, configuration options, and metrics surface from authoritative documentation before implementation.

## Migration Plan

1. Verify the current supported Garage package/module options and select the persistent data directory on Habiki's 4 TB SSD.
2. Provision encrypted administrator credentials and certificate material through the existing secret workflow.
3. Deploy Garage with tailnet-only binding, HTTPS termination, private DNS resolution, and firewall restrictions.
4. Configure monitoring, capacity alerts, and a test isolated bucket/credential.
5. Validate S3 operations and an encrypted test backup from a tailnet client.

**Rollback:** disable the service, revoke project credentials, and remove private DNS/firewall exposure. Retain the persistent data directory until the data-retention decision is explicit.

## Open Questions

- Which dedicated hostname and tailnet DNS mechanism will resolve it to Habiki's tailnet address?
- What capacity threshold and free-space reserve are appropriate for the 4 TB SSD?
- Which backup client and S3 features must be validated first (for example Restic, Kopia, or application-native S3)?
- Should the MinIO administrative console be enabled at all, and if enabled, which tailnet identities may reach it?
