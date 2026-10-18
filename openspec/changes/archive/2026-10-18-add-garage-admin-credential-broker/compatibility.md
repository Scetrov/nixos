# Garage broker implementation checkpoints

## State transport — task 1.3

Inspected `scripts/tofu.sh`: the PostgreSQL backend connects to
`habiki.net.scetrov.live:5433/terraform_state` with `sslmode=verify-full` and
`sslrootcert=/etc/ssl/certs/ca-certificates.crt`. Passwords remain runtime
Vault inputs; no connection credentials were read for this inspection.

Existing live evidence is recorded in
`../archive/2026-10-18-enable-postgresql-acme-tls/live-verification.md`:
verified OpenTofu backend plans before/after TLS-only enforcement and after
reboot exited successfully with no changes; fresh TLS connections verified
hostname/trust and plaintext connections were rejected. This satisfies the
transport prerequisite using the recorded acceptance evidence, not a new live
backend test in this session. Retain verification; do not restore plaintext.

## Proof — 2026-10-18

Habiki's wrapped Garage binary execs `garage-2.4.1`. `scripts/tofu.sh` obtained an Authentik machine JWT and the provider created `minecraft`, `minecraft-backup`, and the read/write/owner=false binding through `https://garage-admin.net.scetrov.live`. `allow_create_bucket` read back false. The only bucket grant was read/write/owner false. An unauthenticated admin request returned 401. Caddy journal lines from the proof window did not contain `Authorization`, `Bearer`, or `AWS4-HMAC`. A path-style upload, list, and read of a proof ZIP succeeded; bucket creation returned 403; the proof object was deleted. A repeat plan reported no changes. The pair was written to the main Vault without printing it.

Saved OpenTofu plans cannot be reused: each wrapper run exchanges a fresh machine JWT, and apply rejects a plan whose token differs.

## Installed versions — task 1.1

The previous note treated `pkgs.garage` 1.3.1 as the declared package. That is
stale. `garage.nix` now sets `package = pkgs.garage_2`, and
`src/roles/nixos/tests/garage-eval.nix` asserts version `2.4.1`. The archived
`upgrade-garage-v2` change records a targeted Habiki deploy of that package.
This session did not SSH to Habiki or read a running generation.

Other declared versions, not store paths from a running generation:

- Authentik image, pinned in `authentik.nix`:
  `ghcr.io/goauthentik/server:2026.8.3`.
- Authentik provider, pinned in `terraform/main.tf`: `goauthentik/authentik`
  `2026.8.0`.
- Caddy: NixOS module uses `services.caddy` with no package override.
  `nixos-26.05` `pkgs/by-name/ca/caddy/package.nix` currently sets `2.11.4`.
  This change does not bump Caddy.

No disposable provider → Authentik → Caddy → Garage fixture has been run.
The management route does not exist yet, and `scripts/tofu.sh` fixture mode
refuses production Vault credentials. Proving the live chain needs the route
from task 2 and an operator-approved wrapper run. Do not treat source
compatibility as that proof.

## Native token scopes — task 1.2, source check only

Garage 2.4 administration API v2 supports user-defined tokens via
`garage admin-token create --scope ...`. The published admin-API manual shows
scopes as endpoint names, including `ListBuckets`, `GetBucketInfo`,
`ListKeys`, `GetKeyInfo`, `CreateBucket`, `CreateKey`, `AllowBucketKey` and
`DenyBucketKey`. The config-file `admin_token` remains an unscoped master
token and is discouraged.

Chosen server-side credential: a dedicated automation token created by
host-local `garage admin-token` / `garage json-api CreateAdminToken`, not the
master `admin_token`. Minimum scope for the Minecraft resources plus the
accepted cross-bucket admin operations:

`ListBuckets,GetBucketInfo,ListKeys,GetKeyInfo,CreateBucket,CreateKey,UpdateKey,AllowBucketKey,DenyBucketKey,UpdateBucket`

`UpdateBucket` is included only if deletion protection is an admin API field
rather than an OpenTofu lifecycle rule. OpenTofu `lifecycle.prevent_destroy`
does not need a Garage scope. Do not add `DeleteBucket` or `DeleteKey`.
Cross-bucket reach of these scopes is accepted for this identity only. This
is not a request to approve an unscoped native token. No token was read,
created, or placed in Caddy.

## Provider and credential persistence — task 1.2, source check only

Selected released provider: `xenOs76/garage` **0.1.1** (registry publication
2026-08-22). It targets Admin API v2 and is the latest release of that
provider.

`d0ugal/garage` 0.2.36 (2026-10-14) is newer but not applicable. Its
`garage_bucket_key` update calls only `AllowBucketKey`. Garage documents that
`false` flags in that call leave the previous permission unchanged; revocation
requires `DenyBucketKey`. That provider also does not expose
`allow_create_bucket`. Using it would violate the false-permission check.

`xenOs76/garage` 0.1.1 `SyncBucketKeyPermissions` reads the current grant and
calls `AllowBucketKey` only for flags that must become true and
`DenyBucketKey` only for flags that must become false. `allow_create_bucket =
false` is sent as `deny.createBucket`, not as an allow flag. That matches the
Garage semantics. Neither provider accepts caller-supplied key material.
`secret_access_key` is computed and present only in create output, then kept
with `UseStateForUnknown`.

Chosen persistence path: capture the provider-generated pair from sensitive
state into the main Ansible Vault. Do not generate a Vault pair and try to
import it through this provider. Vault keys, once implemented:

- `garage_minecraft_access_key_id`
- `garage_minecraft_secret_access_key`

Failed export must retry from the same state values and must not create a
replacement key. List is not a separate Garage permission; read covers list.
The binding is read true, write true, owner false, `allow_create_bucket`
false, and no other bucket grant.

False-permission behaviour is verified from the Garage OpenAPI description and
the provider source at tag `v0.1.1`. It is not yet verified against the
installed Garage process.

## Authentik machine token shape

Proxy forward auth does not accept an app password or Authentik API token as
`Authorization: Bearer`. The outpost expects a JWT from the proxy provider's
OAuth client-credentials flow: `grant_type=client_credentials` with the
provider `client_id` and either `username` plus app password or
`client_secret=<base64(username:app_password)>`. The wrapper must perform that
exchange and pass only the resulting access token to the Garage provider.
Caddy must replace `Authorization` after a successful outpost check. The
native Garage token stays in agenix and is not retrieved by the wrapper.
