## Why

Projects need a durable, self-hosted coordination service for a shared private network without making Habiki itself broadly public. Habiki is the always-on host and can receive a narrowly scoped router port-forward, making it suitable for a permanent Headscale control plane.

## What Changes

- Add a Headscale control-plane service on Habiki with persistent, declaratively managed state.
- Publish only the Headscale HTTPS control endpoint through Caddy on router-forwarded TCP port 8443, using the existing Cloudflare DNS-01 wildcard certificate.
- Establish a single shared tailnet with a secure baseline for node enrolment and access policy.
- Integrate Headscale service health and metrics into the existing monitoring stack.
- Define state recovery and secret-management requirements for Headscale without migrating existing services or project workloads.

## Capabilities

### New Capabilities
- `headscale-control-plane`: A persistent, secure Headscale coordination service for a shared project tailnet.

### Modified Capabilities

None.

## Impact

- Affected NixOS host configuration: Habiki device configuration and new or extended service modules.
- Affected edge configuration: Caddy virtual-host/listener configuration and a router TCP 8443 port-forward managed outside this repository.
- Affected secrets: Cloudflare DDNS credentials and OIDC credentials (if later selected) must use agenix/Ansible Vault workflows. Headscale pre-authentication keys are generated and revoked at runtime by the controller and are never committed.
- New runtime dependency: Headscale and its supported persistent-state backend.
- New observability surface: Headscale health and metrics collected by the existing Grafana/Prometheus stack.
