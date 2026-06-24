## Why

Grafana and OWASP Dependency Track logins are failing through Authentik because deployed OIDC client identifiers can drift from the client IDs managed by OpenTofu. The current deployment flow can render agenix secrets before `src/generated-secrets.yml` has been refreshed from OpenTofu outputs, leaving services with stale or placeholder OIDC configuration.

## What Changes

- Add a deployment safeguard that prevents required OIDC client IDs/secrets for Grafana and Dependency Track from falling back to placeholders or empty values.
- Ensure generated OpenTofu OIDC outputs are available to the secrets/NixOS deployment phase before affected service configuration is rendered.
- Ensure Grafana and Dependency Track receive updated agenix secrets and restart/re-render service environment files when OIDC credentials change.
- Add verification steps that compare service-facing OIDC client IDs with Authentik-managed provider values without exposing secret material.

## Capabilities

### New Capabilities
- `oidc-generated-secret-consistency`: Ensures OpenTofu-managed Authentik OIDC provider credentials are propagated consistently into generated secrets and deployed service configuration.

### Modified Capabilities
- `grafana-resource-monitoring`: Grafana OAuth login requirements change to require the deployed client ID to match the Authentik provider and reject placeholder/stale generated-secret inputs.

## Impact

- Affected systems: Authentik, Grafana, OWASP Dependency Track, agenix secrets, OpenTofu-generated outputs, Ansible deployment orchestration, and NixOS service/container units on Habiki.
- Affected files likely include `scripts/tofu.sh`, `src/playbook.yml`, `src/roles/secrets/tasks/main.yml`, `src/roles/nixos/files/etc/nixos/modules/grafana.nix`, and `src/roles/nixos/files/etc/nixos/modules/dependency-track.nix`.
- No direct runtime/manual service changes should be required; remediation must be delivered through IaC and targeted deploys.
