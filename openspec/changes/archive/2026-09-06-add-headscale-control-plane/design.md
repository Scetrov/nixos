## Context

Habiki is the always-on NixOS host for project infrastructure, but its residential WAN address is dynamic and it has no general public ingress. The existing deployment uses NixOS modules, Podman where appropriate, Caddy, agenix-provisioned secrets, Cloudflare DNS-01 ACME certificates, and Grafana/Prometheus observability.

The new control plane needs to coordinate one shared project tailnet. The user will forward a single router TCP port, 8443, to Habiki. Existing project services are out of scope.

## Goals / Non-Goals

**Goals:**
- Run a durable Headscale control plane on Habiki with state that survives service restarts and NixOS rebuilds.
- Make the control endpoint reachable at a stable HTTPS hostname despite a dynamic WAN address.
- Restrict WAN exposure to the Headscale HTTPS endpoint on TCP 8443.
- Provide a conservative shared-tailnet enrolment and policy baseline.
- Monitor availability and resource health through the existing observability stack.

**Non-Goals:**
- Migrating current services or devices into the tailnet.
- Exposing S3 or other Habiki services to the WAN.
- Providing a DERP relay in the initial release.
- Building a second-site recovery system for Habiki or Headscale state.
- Depending on UniFi Teleport or UniFi-managed WireGuard for controller reachability.

## Decisions

### Run Headscale directly on Habiki with SQLite state

Headscale SHALL run as a NixOS-managed service with a persistent SQLite database and persistent configuration/state directories owned by the service account. SQLite is appropriate for a single-controller deployment and avoids adding a database service solely for Headscale.

**Alternatives considered:** PostgreSQL would add operational complexity and an unnecessary dependency for this single-node controller; containerizing Headscale would be inconsistent with a service that NixOS can manage natively.

### Use Caddy and Cloudflare DNS-01 certificates on an explicit public port

The controller hostname will be a dedicated subdomain under `net.scetrov.live`. Caddy SHALL terminate TLS using the existing Cloudflare DNS-01-managed wildcard certificate and reverse-proxy only the Headscale control endpoint. The router SHALL forward external TCP 8443 to the Caddy listener serving this hostname; the Headscale advertised server URL SHALL include `:8443`.

**Alternatives considered:** Port 443 is unavailable; a VPS relay or outbound tunnel would remove residential ingress but introduces a second permanent infrastructure dependency. A raw Headscale TLS listener would duplicate Caddy's existing certificate and edge-management role.

### Maintain dynamic DNS through Cloudflare

A declaratively managed DDNS service SHALL update the dedicated controller hostname's Cloudflare A and, where applicable, AAAA records when Habiki's WAN address changes. It SHALL use a minimally scoped Cloudflare API token provided through the existing secret workflow.

**Alternatives considered:** Manual DNS updates cause avoidable controller outages after WAN address changes; relying on the router's vendor-specific DDNS integration would make the control plane dependent on UniFi behavior.

### Separate controller authentication from generic proxy authentication

Caddy SHALL NOT apply the existing Authentik `forward_auth` pattern to Headscale protocol traffic. Headscale's configured enrolment method and access policy SHALL control node admission. Initial policy SHALL deny unapproved access by default and use explicit node tags or ownership identities for administrative/project separation. Operators SHALL create expiring reusable pre-authentication keys through the local Headscale CLI and revoke them through the controller when no longer needed; these runtime-generated keys SHALL NOT be stored in agenix or committed to the repository.

**Alternatives considered:** Proxy-level interactive authentication can interrupt protocol clients and does not replace Headscale node authorization. Fully open pre-authentication keys are unacceptable for a long-lived controller.

### Defer embedded DERP

The initial service SHALL use Headscale's normal coordination behavior without operating an embedded DERP relay. Direct connectivity and the need for relay fallback will be observed before opening additional UDP ingress.

**Alternatives considered:** Embedded DERP can improve restrictive-NAT connectivity but needs additional UDP 3478 exposure and public-address configuration.

## Risks / Trade-offs

- [Residential WAN address or router forwarding is unavailable] → DDNS limits stale-address time; document router forwarding as an external prerequisite and alert on public endpoint availability.
- [TCP 8443 is scanned or attacked] → expose only the TLS-protected Headscale endpoint, keep Headscale on loopback/private networking, rate-limit where supported, and keep enrolment credentials in agenix-managed secrets.
- [Headscale state is lost with Habiki] → state survives normal rebuilds; this change explicitly accepts that full host loss requires recreating the control plane and re-enrolling nodes.
- [NAT traversal is insufficient] → observe connection behavior first; add a DERP-specific change only if justified.
- [Unintended tailnet lateral access] → begin from default-deny policy and introduce explicit tags/ACLs as project requirements are known.

## External Prerequisite

The network operator has configured the external router to forward TCP 8443 to Habiki TCP 8443. Router credentials are managed outside this repository. The NixOS firewall and Caddy listener in this change accept only the Headscale HTTPS endpoint on that port. Public HTTPS was validated from an external path during deployment. Continuous external synthetic monitoring is deferred because the available on-host probe cannot hairpin through the router; Prometheus monitors the local Headscale service and TLS edge instead.

## Migration Plan

1. Provision secrets and DNS permissions through the existing encrypted secret workflow.
2. Deploy Headscale, persistent storage, Caddy route/listener, and DDNS update service to Habiki.
3. Configure the router's external TCP 8443 forwarding to Habiki and verify the dedicated hostname resolves to the current WAN address.
4. Validate the public TLS control endpoint, enrol a test node, and validate the default policy boundary.
5. Enable monitoring and alerts, then retain the service configuration as the durable base for future project enrolment.

**Rollback:** remove the router port-forward, disable the NixOS service and Caddy listener, and revoke Headscale enrolment credentials. Persistent state is retained unless intentionally removed.

## Open Questions

- What dedicated hostname under `net.scetrov.live` should be used?
- Does the ISP provide usable IPv6, and if so, should the controller publish an AAAA record in addition to IPv4?
- What minimal alerting threshold defines an unacceptable DDNS/controller reachability interruption?
