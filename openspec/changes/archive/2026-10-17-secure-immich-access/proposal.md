## Why

Immich still opens port 3000 directly and has no Caddy or Authentik integration, leaving security finding SR-007 and GitHub issue #30 unresolved. It is currently unused, so we can establish the standard HTTPS/OIDC access path without migrating existing users.

## What Changes

- Serve `https://immich.net.scetrov.live` through Caddy and bind Immich to loopback without opening its application port in the firewall.
- Add a native Authentik OIDC provider/application using existing OpenTofu patterns, with credentials delivered through existing runtime secret automation.
- Keep browser, mobile, API, upload and realtime access working without a second proxy-auth gate.
- Retain local administrator recovery and add focused checks and short operator documentation.
- Do not migrate existing users, reset storage, upgrade Immich, introduce new infrastructure, or redesign shared authentication/proxy modules.

## Capabilities

### New Capabilities

- `immich-secure-access`: HTTPS-only proxied access, native Authentik sign-in, runtime credential handling and administrator recovery for Immich.

### Modified Capabilities

None.

## Impact

- Primarily `src/roles/nixos/files/etc/nixos/modules/immich.nix`, `terraform/authentik.tf`, and the existing vault-to-runtime secret provisioning path.
- Add a small Immich operator document and focused regression checks using existing test conventions.
- Reuse the existing hostname mapping, certificate automation, Caddy service and Authentik deployment on Habiki; do not add public ports or dependencies.
- OpenTofu operations remain restricted to `scripts/tofu.sh`; deployment uses targeted Ansible/NixOS automation.
- Closes https://github.com/Scetrov/nixos/issues/30 after deployed verification, not merely configuration changes.
