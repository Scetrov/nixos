## 1. Service and persistent state

- [x] 1.1 Verify the current supported Headscale package and NixOS module options from authoritative release and NixOS documentation.
- [x] 1.2 Add a NixOS module that configures Headscale with persistent SQLite state, private service networking, and hardened service ownership.
- [x] 1.3 Import and enable the Headscale module from Habiki's device configuration.
- [x] 1.4 Document the runtime-generated, expiring reusable pre-authentication-key workflow without committing or agenix-provisioning key material.

## 2. Public controller ingress and DNS

- [x] 2.1 Configure a dedicated Headscale hostname and Caddy HTTPS reverse proxy listener using the existing Cloudflare DNS-01 certificate.
- [x] 2.2 Configure the Headscale advertised server URL for the dedicated hostname and external TCP port 8443.
- [x] 2.3 Add a declaratively managed Cloudflare DDNS updater with least-privilege, agenix-provisioned credentials.
- [x] 2.4 Configure the external router TCP 8443 to Habiki port-forward and record the external prerequisite without storing router credentials in the repository.

## 3. Tailnet security baseline

- [x] 3.1 Select and configure the initial authorised enrolment workflow, including expiration/revocation handling where supported.
- [x] 3.2 Create a default-deny Headscale policy with explicit administrative and project tag/ownership boundaries.
- [x] 3.3 Verify that Caddy does not apply generic Authentik proxy authentication to Headscale protocol traffic.

## 4. Observability and validation

- [x] 4.1 Integrate Headscale health and supported metrics with the existing Prometheus/Grafana stack.
- [x] 4.2 Add an availability check or alert for the public Headscale HTTPS endpoint and the local service.
- [x] 4.3 Add NixOS evaluation tests for module wiring, persistent state configuration, private backend binding, and narrow ingress.
- [x] 4.4 Deploy with a targeted Habiki NixOS run and validate HTTPS reachability, DNS update behavior, authorised enrolment, default-deny access, and state retention after restart.
