## Context

Garage administration is bound to `127.0.0.1:3903` on Habiki. Existing Caddy configuration already provides private-network admission, TLS and Authentik forward authentication. `scripts/tofu.sh` loads Vault credentials and uses PostgreSQL remote state. We will extend those patterns, not introduce a separate management platform.

The end-to-end compatibility of the Garage provider with Authentik's proxy-provider bearer tokens has not been demonstrated. That is the first implementation checkpoint.

## Goals / Non-Goals

**Goals:** Make one private management route and use it to provision a `minecraft` bucket with a dedicated read/list/write key for manually uploading, inspecting and pruning Minecraft backup ZIPs from the operator's laptop (replacement for cloud Drive storage), storing the pair in Vault.

**Non-Goals:** Public administration, changes to existing S3 clients, per-bucket administrative isolation, immutable backups, SSH tunnels or Authentik-backed SSH integration, interactive browser/MFA login for provisioning, a custom request-filtering gateway, new dashboards/alerts, general rotation infrastructure or broad backend hardening.

## Decisions

### 1. Prove the authentication chain before building around it

Use a small disposable test with the selected released provider and installed service versions:

```text
scripts/tofu.sh → Authentik machine token
       |
       v
Garage provider → HTTPS Caddy → Authentik authorisation
                            |
                            v
                   replace bearer credential
                            |
                            v
                   Garage loopback API
```

Verify token exchange, application-policy enforcement and provider acceptance of the token. If incompatible, stop and revise this design; do not fall back to exposing the native Garage token.

### 2. Reuse existing private Caddy conventions

Add `garage-admin.net.scetrov.live` with internal DNS/hosts mapping and trusted TLS. Reuse the existing internal S3 socket-peer ranges (`10.229.0.0/16`, `127.0.0.0/24`, `100.64.0.0/10`) rather than maintaining a new workstation allowlist. Forwarded headers cannot grant admission; IPv6 remains denied. Do not open direct Garage ports or change existing S3 routes.

The agreed architecture retains the private Caddy broker rather than a wrapper-managed SSH tunnel. Do not introduce an SSH authentication integration or custom authentication bridge.

Create one dedicated Authentik machine identity/application policy. Caddy requires its valid bearer authentication, asks the outpost to authorise it, then overwrites upstream Authorization with a Garage token supplied through Vault/agenix. Use an explicitly ordered route with a fixed loopback upstream. Missing/invalid credentials and Authentik failure must not reach Garage. The wrapper authenticates using the dedicated Vault-backed machine credential without browser login or an operator MFA challenge. OpenTofu receives only the resulting Authentik token; the native Garage token stays server-side and is never retrieved by the wrapper.

Use a dedicated native Garage automation token restricted to the required resource operations if the installed release supports scopes. Verify this in the compatibility check. If scopes are unavailable, document the broader authority and obtain approval before deployment. Do not add a second, provider-specific method/path firewall in Caddy. This route is an administrative interface, not a bucket-scoped security boundary. Cross-bucket administrative reach is explicitly accepted for the dedicated infrastructure-administration identity, even when operation scopes are available. Never distribute that identity or its credentials to Minecraft. This acceptance does not waive the separate approval gate for an unscoped native token.

### 3. Keep provisioning in the existing wrapper

Configure a compatible Garage provider under existing version/integrity policy. All OpenTofu commands use `scripts/tofu.sh`. Add only the necessary machine-token acquisition and sensitive provider inputs; keep local fmt/validate and fixture modes credential-free.

Bootstrap Authentik and the Caddy route before applying Garage resources, so initial identity provisioning does not require a working Garage connection. Provision any server-side Garage token through host-local automation, not through the public-facing route. Use targeted Habiki/component deployment, not an unrestricted all-host run.

OpenTofu owns the `minecraft` bucket, dedicated key and binding: read, list and write enabled, owner disabled, no bucket-creation permission or other bucket grants. Verify the provider handles false permission values correctly; do not assume an allow call revokes prior grants. Do not overwrite or adopt an existing bucket/key without reviewing ownership. Protect the bucket against accidental deletion.

### 4. Use the simplest supported Vault persistence path

Determine the provider's key-resource behaviour during the compatibility check. If it supports supplying key material at creation, use an idempotently generated Vault pair as sensitive input. Otherwise capture its sensitive generated output into the main Ansible Vault through the wrapper. Document the chosen Minecraft-specific Vault keys.

Reuse existing encrypted-secret helpers where possible. Preserve unrelated Vault values, write the encrypted result atomically, and never print the pair or persist plaintext in the repository. If apply succeeds but Vault export fails, report failure and recover the same pair from state rather than creating a replacement key. An unchanged run must preserve the credentials.

The state necessarily contains sensitive material. Check existing backend protection before applying: the current `sslmode=disable` setting does not itself establish an encrypted connection. If there is no protected transport, pause for a separately agreed fix. This change does not redesign the state platform or its backups.

### 5. Small, concrete acceptance check

Verify the real provider chain, rejected unauthorised requests and fail-closed Authentik behaviour. After targeted deployment, apply through the wrapper and confirm Vault persistence, a no-change plan, and S3 behaviour using `https://s3.net.scetrov.live`, region `garage`, path-style addressing:

- Upload, read and list on `minecraft` succeed.
- Access to an unrelated test bucket and bucket creation fail.
- Effective permissions are read/list/write only, with no owner, bucket creation or additional grants.

Keep existing logging and ensure it does not record bearer tokens or secret-bearing bodies. Add focused regression tests for wrapper authentication, Vault persistence failure and permission configuration; do not build a general-purpose security test platform.

## Risks / Trade-offs

- [Caddy holds Garage authority] → Use the existing restricted secret-delivery pattern and a dedicated scoped token where available; acknowledge that management authority can affect more than Minecraft.
- [Provider/Authentik incompatibility] → Resolve with the initial disposable test before deployment.
- [Token expiry interrupts apply] → Fail closed and rerun with a fresh token; no authentication bypass or refresh daemon.
- [Vault export fails after key creation] → Recover the existing state value; do not rotate implicitly.
- [Bucket access is mistaken for immutable backup] → Overwriting and deleting ZIPs is intended Drive-style behaviour, not a compromise. Document that the key is not immutable backup protection; irreplaceable data needs a separate recovery mechanism.

## Migration Plan

1. Verify compatibility, native token scope support and current state transport; choose the credential persistence path.
2. Add the dedicated Authentik identity and deploy the private Caddy route using existing automation.
3. Review and apply the Minecraft resources through the wrapper, persist credentials in Vault, and run the acceptance checks.
4. Update Garage usage/recovery documentation and run existing quality gates.

Rollback disables the new management route and dedicated identity/token. Preserve the bucket, objects, Vault pair and state; do not run a broad destroy. Existing S3 endpoints remain available.

## Open Questions

- Which compatible released provider works with the installed Garage API and Authentik token exchange?
- Does the installed Garage support scoped automation tokens?
- Does the provider accept supplied key material, or must the wrapper capture generated output?
- Is the existing backend connection protected independently of PostgreSQL TLS?

These are bounded implementation checkpoints, not reasons to add new platform subsystems.
