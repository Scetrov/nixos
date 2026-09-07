# Garage tailnet backup target

Habiki provides the private S3 endpoint `https://s3.tailnet.net.scetrov.live` to
Headscale clients only. It is a single-host backup target, not disaster
recovery: data is stored on Habiki's SSD and is not replicated off-host.

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
Do not use `garage key info --show-secret` in automation or logs. The initial
`reapers-arsenal` project follows this pattern.

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
