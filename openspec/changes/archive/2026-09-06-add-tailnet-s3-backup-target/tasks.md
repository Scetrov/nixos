## 1. Storage and service foundation

- [x] 1.1 Verify the supported Garage release and NixOS packaging/module options using authoritative documentation before adding the dependency.
- [x] 1.2 Select and document the persistent Garage data and metadata directories on Habiki's 4 TB SSD, including service ownership and filesystem-safe permissions.
- [x] 1.3 Add a NixOS module that configures Garage with persistent data, hardened service ownership, and no anonymous access.
- [x] 1.4 Import and enable the Garage module from Habiki's device configuration.

## 2. Private networking and TLS

- [x] 2.1 Enroll Habiki as an initial Headscale node and record its assigned tailnet IPv4 address before configuring the S3 endpoint (`100.64.0.1`).
- [x] 2.2 Select the dedicated S3 hostname and configure tailnet DNS to resolve it to Habiki's Headscale address (`s3.tailnet.net.scetrov.live` → `100.64.0.1`).
- [x] 2.3 Provision trusted HTTPS certificate material through the encrypted secret workflow and configure the S3 API to use it.
- [x] 2.4 Bind the S3 API only to Habiki's tailnet address and required local management paths.
- [x] 2.5 Add firewall policy that permits API access only from the tailnet and confirms no WAN listener, Caddy public route, or router port-forward is created.
- [x] 2.6 Decide whether the administrative console is required; if enabled, apply the same tailnet-only and identity restrictions (not required; Garage admin API remains loopback-only).

## 3. Credentials and bucket isolation

- [x] 3.1 Add agenix-backed secret declarations for distinct Garage administrative and project credentials without committing secret material.
- [x] 3.2 Implement a repeatable provisioning path for isolated project buckets and least-privilege bucket-scoped policies.
- [x] 3.3 Document credential rotation and revocation procedures for project backup clients.

## 4. Observability and validation

- [x] 4.1 Integrate Garage health and supported metrics with the existing Prometheus/Grafana stack.
- [x] 4.2 Configure visible capacity monitoring and an alert threshold that preserves the agreed free-space reserve on Habiki's SSD.
- [x] 4.3 Add NixOS evaluation tests for persistent storage, private binding, firewall restrictions, encrypted secret injection, and disabled anonymous access.
- [x] 4.4 Deploy with a targeted Habiki NixOS run and validate trusted HTTPS, tailnet-only access, bucket isolation, an authorized S3 upload/download, and capacity telemetry.
- [x] 4.5 Validate an encrypted test backup from the first future project's selected backup client before treating the target as operational.
