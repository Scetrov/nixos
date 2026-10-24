# Garage private backup target

Habiki provides two private HTTPS S3 endpoints:

| Endpoint | Internal address | Allowed socket peers |
| --- | --- | --- |
| `https://s3.tailnet.net.scetrov.live` | `100.64.0.1` | Headscale IPv4 clients (`100.64.0.0/10`) only |
| `https://s3.net.scetrov.live` | `10.229.10.2` | LAN (`10.229.0.0/16`), loopback (`127.0.0.0/24`) and tailnet (`100.64.0.0/10`) |

Configure S3 clients with region `garage`, **path-style addressing**, and the
chosen endpoint URL. Both endpoints use the same existing Garage credentials
and bucket permissions; neither adds browser SSO or anonymous bucket access.
Forwarded headers do not grant network admission. IPv6 peers, including `::1`,
are not allowed.

The LAN hostname resolves through the existing internal DNS/hosts mapping and
requires a route to `10.229.10.2`, even for tailnet clients. Tailnet-only clients
without LAN routing must continue using `https://s3.tailnet.net.scetrov.live`;
no client changes or subnet routing are required for that endpoint. Habiki-local
tests may resolve the LAN hostname to `127.0.0.1` while retaining its hostname
for TLS verification and S3 signatures.

This is a single-host backup target, not disaster recovery: data is stored on
Habiki's SSD and is not replicated off-host. Persistent service state is beneath
`/var/lib/garage`; ordinary restarts/rebuilds/disablement preserve it. The module
selects `pkgs.garage_2`, and its evaluation checks the intended package version;
do not revive the superseded `pkgs.garage` alias from an old upgrade plan.
Direct S3/RPC/admin/metrics listeners stay loopback-only with no router forwards.

## Minecraft operator backups

The `minecraft` bucket replaces a cloud Drive folder for manually uploading,
inspecting and pruning Minecraft backup ZIPs from the operator's laptop. It is
not immutable backup storage. The dedicated key may overwrite and delete
objects; that is the intended Drive-style behaviour. Irreplaceable data needs
a separate recovery mechanism.

Client settings:

| Setting | Value |
| --- | --- |
| Endpoint | `https://s3.net.scetrov.live` |
| Region | `garage` |
| Addressing | path-style |
| Bucket | `minecraft` |

The access key ID and secret are the main Vault entries
`garage_minecraft_access_key_id` and `garage_minecraft_secret_access_key`.
OpenTofu stores the same pair as sensitive remote-state values. Do not give
the pair, the Authentik management identity, or the native Garage token to the
Minecraft server, backup automation, or any other client.

The key has read, list and write on `minecraft` only. Owner and bucket-creation
authority are disabled. List is part of Garage's read permission; there is no
separate list flag. `xenOs76/garage` 0.1.1 sends `DenyBucketKey` for a false
permission and `deny.createBucket` for `allow_create_bucket = false`, because
Garage ignores false flags on `AllowBucketKey`.

If apply creates the key but Vault persistence fails, rerun `scripts/tofu.sh`.
The wrapper reads the existing sensitive state output and writes that same pair.
It will not create a replacement key. A Vault entry that already differs is left
unchanged and reported as a failure.

## Private administration route

`https://garage-admin.net.scetrov.live` is a private Caddy broker for OpenTofu.
Admission uses the socket peer ranges above, not forwarded headers. IPv6 peers
are denied. After Authentik authorises the dedicated `garage-admin-broker`
machine JWT, Caddy replaces `Authorization` with the server-side scoped Garage
automation token. That native token stays in the Vault entry
`garage_admin_automation_token` and the agenix file
`garage_admin_automation_token.age`. The wrapper never retrieves it.

The machine identity is infrastructure administration, not a Minecraft
credential. Its scoped token can manage buckets and keys beyond `minecraft`.
That cross-bucket reach is accepted only for this identity. It is not approval
to use the unscoped config-file `admin_token`. If a future Garage package
cannot scope tokens, stop and obtain approval before deploying that token.

Rollback disables this route, the Authentik application/outpost binding, and
the automation token. Do not destroy the bucket, objects, Vault pair, or
remote state. Existing S3 endpoints remain available.

Recovery of the operator pair is the Vault entry above, or the sensitive
OpenTofu state output if Vault persistence failed. Do not run `garage key info
--show-secret` or print provider output.

## Verification and compatibility

The 2026-10-18 LAN endpoint acceptance recorded signed listing, PUT, byte-exact
GET/DELETE and a 6 MiB multipart transfer, with normal TLS verification.
Anonymous/invalid signatures failed. Disallowed IPv4/IPv6 socket sources were
denied even with spoofed forwarded headers. Both DNS resolvers converged.
Tailnet-source tests originated on Habiki; no separate tailnet-only client or
external-WAN denial test was performed. Those are coverage limits, not passed
remote-client checks.

The later broker proof used Garage 2.4.1 and verified authenticated OpenTofu
provisioning, read/write with owner/bucket-creation disabled, unauthenticated
admin 401, a successful proof-object transfer/cleanup, encrypted Vault export
and a no-change repeat plan. The earlier LAN smoke test used the then-running
v1 API; it is not authority to downgrade the current broker/provider contract.
Backend transport is `verify-full`; see [PostgreSQL TLS](postgresql-tls.md).

Each wrapper invocation exchanges a fresh Authentik machine JWT. A saved plan
cannot be reused across wrapper invocations when its provider token differs;
review/apply using the supported wrapper workflow. Native token scopes are
endpoint-scoped, not bucket-scoped; keep the accepted infrastructure-only
cross-bucket authority distinct from the Minecraft key's narrow permissions.

## Provisioning a project bucket

`src/roles/nixos/tasks/garage-provisioning.yml` is the authoritative,
idempotent provisioning path. Each project needs:

1. A dedicated agenix credential file named
   `garage_<project>_s3_credentials.age`, containing only:

   ```sh
   GARAGE_<PROJECT>_ACCESS_KEY_ID=<20-character access key ID>
   GARAGE_<PROJECT>_SECRET_ACCESS_KEY=<secret access key>
   ```

2. A matching declaration in `src/roles/secrets/files/secrets/secrets.nix` and
   a NixOS `age.secrets` declaration with mode `0400`.
3. A project entry in `garage-provisioning.yml` that creates the bucket when
   absent, imports the pre-generated key only when it is absent, and grants
   only `--read --write --owner` for that bucket:

   ```sh
   garage bucket create <project>
   garage key import -n <project>-backup "$ACCESS_KEY_ID" "$SECRET_ACCESS_KEY" --yes
   garage bucket allow --read --write --owner <project> --key "$ACCESS_KEY_ID"
   ```

Never create a shared project key or allow a key on another project's bucket.
Do not use `garage key info --show-secret` in automation or logs.

## Rotate or revoke a project credential

1. Generate a new access-key ID and secret locally; do not place either in a
   Nix expression, inventory, shell history, or task output.
2. Re-encrypt the replacement pair through the existing Ansible Vault →
   agenix workflow and deploy the secret to Habiki with a targeted secrets run.
3. Import the replacement key, grant it only the intended bucket permissions,
   and verify an S3 upload/download using the new key from a tailnet client.
4. Update the backup client, then revoke the retired key with
   `garage key delete <old-access-key-id>` and confirm it can no longer read
   or write the bucket.
5. If an exposure is suspected, revoke first, create a new credential, and
   inspect Garage and backup-client logs before restoring client access.

Garage RPC, administration, and metrics tokens are independent encrypted
secrets. Rotate them separately through the same workflow; restart the
relevant systemd service after changing the server tokens and update
Prometheus' bearer-token file atomically with a metrics-token rotation.

## Capacity and health monitoring

Prometheus scrapes Garage's authenticated loopback metrics endpoint and raises
`GarageServiceUnavailable` when it cannot be scraped for five minutes. The
existing System Resources dashboard exposes Habiki's root filesystem free space;
`GarageStorageReserveLow` fires after 15 minutes below the agreed 500 GiB
(536,870,912,000 byte) reserve. Garage's persistent data and metadata are both
beneath this filesystem, so this threshold preserves recovery space for the
backup target without implying off-host durability.
