## Why

Provide a private, lightweight Git forge for personal code and experiments on Habiki. The service should reuse existing home-network access, Authentik identity, and declarative deployment rather than introduce a publicly exposed or highly available platform.

## What Changes

- Deploy Forgejo on Habiki at `https://source.net.scetrov.live`, behind Caddy using the existing wildcard certificate, with SQLite and persistent repository storage.
- Add the FQDN to Habiki's shared `local-networking.nix` host entry so both Habiki and Fyne Blocky instances resolve it to `10.229.10.2`; create no public DNS record.
- Provide Git SSH on a dedicated TCP port 2222 without changing administrative SSH.
- Configure native Authentik OIDC, restricted initially to the owner's identity through a dedicated access group; disable open registration.
- Disable Forgejo Actions and defer CI/runner deployment. Retain experimental runner code disabled for a separately scoped future change.
- Automate Authentik resources, secret propagation, Forgejo authentication-source reconciliation, and targeted deployment. Add service logs, metrics, and health visibility to the existing Grafana stack.
- Validate existing LAN, Teleport, and Headscale connectivity without expanding Headscale routes or ACLs unless a separately agreed networking change is required.

## Capabilities

### New Capabilities

- `forgejo-private-service`: Private HTTPS and Git SSH service, local DNS integration, persistent lightweight storage, and declarative lifecycle.
- `forgejo-authentik-access`: Automated native OIDC sign-in restricted to the owner, with service-native SSH and token authentication.
- `forgejo-observability`: Forgejo logs, protected metrics, and actionable service-health visibility.

### Modified Capabilities

- `oidc-generated-secret-consistency`: Extend authoritative generated OIDC secret handling, validation, deployment ordering, and safe verification to Forgejo alongside Grafana and Dependency Track.

## Impact

- Host configuration: `src/roles/nixos/files/device-configuration/habiki.nix`, the Forgejo module, shared `local-networking.nix`, Caddy, Prometheus, and existing log collection integrations.
- Deployment: `src/playbook.yml`, relevant Ansible roles, `scripts/play.sh`, and the secure `scripts/tofu.sh` workflow where necessary for a targeted Forgejo deployment.
- Identity: Authentik resources in `terraform/`, sensitive outputs and generated-secret propagation, encrypted inputs derived from `src/secrets.yml` and deployed through agenix.
- Dependencies: Forgejo. Select a supported release during implementation, verify integrity, and follow repository update policy. Runner/runtime/action/image selection is deferred.
- Network: HTTPS through the existing listener and dedicated Git SSH TCP 2222, limited to intended private access. Both DNS hosts need the shared alias update.
- State: Persistent SQLite, repositories, LFS/attachments where enabled, and service keys; no HA or formal backup guarantees. No changes to existing Git hosting or repositories are implied.
