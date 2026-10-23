## Why

Provide enrolled users with convenient browser-based, full read/write access to their existing `$HOME/Documents` directories on Habiki using Authentik SSO. Some participating Unix accounts do not yet exist, and the current Filebrowser module is only a package installation stub rather than a deployed service.

## What Changes

- Deploy one shared FileBrowser Quantum instance on Habiki behind Caddy with native Authentik OIDC and an explicit application-access group.
- Declare an enrollment mapping between explicitly selected Authentik identities, Unix usernames, and Quantum scopes; initial Unix usernames are `scetrov`, `pinkgiraffes`, and `flyingfire` (exact lowercase spelling). Provision missing approved Unix accounts and Documents directories through automation, and map each Authentik identity to the exact corresponding `preferred_username` claim.
- Bind-mount only enrolled users' literal Documents directories and grant each Quantum user full file-operation access only to their own scope. Do not exclude subdirectories based on their names.
- Use a non-root shared service identity and managed access/default ACLs so Unix users and Quantum can manage each other's files. Browser uploads may remain owned by the service identity; per-user process isolation and Unix impersonation are not required.
- Reconcile application scopes and enrollment through automation and deny unmapped identities. Automated offboarding is explicitly deferred for this initial family rollout; reject enrollment removals fail-closed rather than silently retaining access.
- Integrate service logging and health monitoring with the existing Grafana stack and document operation and recovery.

## Capabilities

### New Capabilities

- `filebrowser-documents-service`: Shared Quantum runtime, explicit identity enrollment, native SSO, per-user Documents authorization, filesystem interoperability, and operational lifecycle.

### Modified Capabilities

None. Existing services retain their current requirements.

## Impact

- NixOS: replace or retire `modules/user-scetrov-filebrowser.nix`; add the Quantum service, enrollment/account integration, ACL management, and Habiki configuration.
- Networking and observability: Caddy, device host aliases and `local-networking.nix`, and existing Alloy/Grafana provisioning where needed.
- OpenTofu: add Authentik application/provider, group/policy, and any provider-specific claim mapping; run exclusively through `scripts/tofu.sh`.
- Ansible: extend vault-backed runtime secret delivery and targeted orchestration for the service and declarative application-state reconciliation.
- New runtime dependency: FileBrowser Quantum `v2.1.3-beta`, pinned for Habiki's amd64 platform to `ghcr.io/gtsteffaniak/filebrowser@sha256:989e2dc6c491bda3c8bb82b27cd7798924ff3025cabdcad2444eb42f774836f6` (registry manifest verified 2026-10-23). The operator approved this release-track/digest update and the under-seven-day CVSS 8.8 security-fix exception; deployment still requires disposable isolation tests.
- Personal data remains under each Unix home. File ownership from browser uploads can differ from local uploads, as explicitly accepted; Linux ownership is not tied to the OIDC session.
