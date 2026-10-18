## Why

Provision a `minecraft` bucket and a dedicated read/list/write S3 credential so the operator can manually upload, inspect and prune Minecraft backup ZIPs from their laptop through the existing S3 endpoint, as a replacement for cloud Drive storage, without exposing Garage's native administration token to the provisioning client. Garage's API currently listens only on Habiki loopback, so OpenTofu needs a private, authenticated management route.

## What Changes

- First verify that the selected Garage provider works through Authentik machine authentication and Caddy credential substitution.
- Add `garage-admin.net.scetrov.live` using existing private-network admission, TLS, Authentik and Vault/agenix conventions. Keep Garage's direct listeners and existing S3 endpoints unchanged.
- Let a dedicated Vault-backed Authentik machine identity use the route without interactive login; Caddy replaces its bearer token with a server-side Garage automation token. OpenTofu receives only the Authentik token, never the native Garage token.
- Extend `scripts/tofu.sh` minimally for this authentication and provision the bucket, dedicated key and its read/list/write permission through OpenTofu.
- Store the access key and secret in Ansible Vault and sensitive remote state. Verify upload, read and list, denied cross-bucket access, and an unchanged repeat plan.

## Capabilities

### New Capabilities

- `garage-admin-broker`: Private Caddy management access authorised by Authentik, with server-side Garage credentials.
- `garage-minecraft-provisioning`: Wrapper-only OpenTofu provisioning of the Minecraft bucket and Vault-backed dedicated credentials.

### Modified Capabilities

None. Existing `tailnet-s3-backup-target` requirements remain unchanged.

## Impact

Touches the existing Caddy/DNS/secret configuration, Authentik resources, OpenTofu provider/resources, wrapper, tests and Garage documentation. Uses existing logging and deployment tooling; does not introduce a custom API gateway, new alerts, general credential-rotation framework or platform-wide state-security project.

The agreed approach is the private Caddy broker, not an SSH tunnel or Authentik-backed SSH integration. The dedicated administrative identity may manage resources beyond Minecraft; it must never be distributed to the Minecraft server or any client. The bucket's S3 key is intended for the operator's laptop backup workflow. This accepts cross-bucket management authority, not implicit approval of an unscoped native token.

Provider selection must follow existing dependency policy. Check the current PostgreSQL state transport before adding credentials: `sensitive` hides normal output but does not encrypt state. If protection is inadequate, report the prerequisite and agree on a separate remediation rather than silently expanding this change.
