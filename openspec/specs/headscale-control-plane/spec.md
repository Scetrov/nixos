# headscale-control-plane Specification

## Purpose

Defines the persistent, externally reachable Headscale control plane on Habiki.

## Requirements

### Requirement: Persistent Headscale controller

The system SHALL run one Headscale control-plane service on Habiki. Its configuration and SQLite state SHALL use persistent, service-owned storage that survives service restarts and NixOS rebuilds.

#### Scenario: Service restart preserves controller state

- **WHEN** the Headscale service is restarted or Habiki is rebuilt
- **THEN** the service SHALL start using its existing persistent state
- **AND** previously enrolled nodes SHALL remain known to the controller

### Requirement: Stable externally reachable controller endpoint

The system SHALL publish the Headscale control API at a dedicated `net.scetrov.live` hostname over HTTPS. Caddy SHALL terminate TLS using the existing Cloudflare DNS-01 certificate workflow and proxy only controller traffic to Headscale. The advertised controller URL SHALL use TCP port 8443.

#### Scenario: Remote node reaches the controller

- **WHEN** a remote node resolves the dedicated controller hostname
- **THEN** the hostname SHALL resolve to Habiki's current WAN address
- **AND** a connection to HTTPS TCP port 8443 SHALL reach the Headscale control API through Caddy

### Requirement: Dynamic DNS maintenance

The system SHALL automatically maintain the dedicated Headscale hostname's Cloudflare DNS address records when Habiki's WAN address changes. DNS credentials SHALL be supplied through the repository's encrypted secret-management workflow and SHALL be scoped only to the necessary DNS update permissions.

#### Scenario: WAN address changes

- **WHEN** Habiki's router WAN address changes
- **THEN** the dynamic-DNS service SHALL update the controller hostname's applicable Cloudflare address records
- **AND** the controller hostname SHALL converge to the new reachable address without manual DNS modification

### Requirement: Narrow ingress and controller-owned admission

The router-facing listener SHALL expose only the TLS-protected Headscale endpoint on TCP port 8443. Caddy SHALL NOT require Authentik proxy authentication for Headscale protocol requests. Headscale SHALL require an explicit authorized enrolment mechanism and SHALL enforce a default-deny tailnet access baseline.

#### Scenario: Unauthorised network client reaches Habiki

- **WHEN** an internet client connects to Habiki through the forwarded port
- **THEN** it SHALL be able to reach only the Headscale HTTPS endpoint
- **AND** it SHALL NOT gain access to other Habiki services through that listener

#### Scenario: Unauthorised node attempts enrolment

- **WHEN** a node lacks valid Headscale enrolment authorization
- **THEN** Headscale SHALL reject the enrolment
- **AND** the node SHALL NOT receive tailnet access

### Requirement: Controller observability

The system SHALL collect Headscale service availability and supported operational metrics through the existing monitoring stack. The system SHALL make loss of controller availability observable to operators.

#### Scenario: Controller becomes unavailable

- **WHEN** Headscale or its public HTTPS endpoint becomes unavailable
- **THEN** monitoring SHALL record the failed availability condition
- **AND** the condition SHALL be visible through the existing Grafana-based observability tooling
