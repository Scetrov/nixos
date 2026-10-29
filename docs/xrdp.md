# Bullit XRDP PKI

Bullit provides independent Plasma X11 remote-login sessions. TLS uses the
existing private CA; client trust is **not** changed by CRL publication.

## Trust and custody

- The CA certificate/key and dedicated CRL publisher identity are authoritative
  in encrypted `src/secrets.yml`: `xrdp_ca_cert`, `xrdp_ca_key`, and
  `xrdp_crl_publisher_key`. Agenix recipients include only operator keys and
  Bullit's host key (`devenv` in `secrets.nix`), not Habiki or Fyne.
- The CA private key stays `0400 root:root` on Bullit. Root compromise of Bullit
  can issue certificates trusted by clients of this CA. Use this CA only for
  XRDP, not as a general-purpose trust anchor.
- Import only [`certs/bullit-xrdp-ca.crt`](certs/bullit-xrdp-ca.crt) into clients'
  trusted root store, verifying this SHA-256 fingerprint independently:

```text
E8:A9:B7:96:DB:A9:B3:2A:DA:65:50:24:AB:10:A0:02:E7:2B:4B:FB:C2:6F:6E:DC:69:5A:53:FF:86:79:F2:C2
```

Connect using `bullit`, `bullit.net.scetrov.live`, or `10.229.10.10`, the leaf SANs
and existing aliases. Clients must validate both the signature and hostname/IP.
Do not disable certificate validation or revocation checking to hide warnings.

## Issuance and publication contract

`xrdp-tls-renew.service` serializes operations using a filesystem lock. Its
persistent daily timer has up to one hour jitter; preparation also runs before
XRDP starts. Agenix on this host decrypts during activation, not through an
`agenix.service` dependency. Root performs signing; xrdp cannot read issuer state.

The durable OpenSSL CA database is `/var/lib/xrdp-ca` (`0700`), separate from
runtime agenix material and the TLS pair. Missing/partial state or a different
CA fingerprint fails closed, requiring explicit recovery. Never initialize an
empty database to make an existing deployment start.

Leaves use fresh RSA-3072 keys, server-only EKU, the three SANs, and a 365-day
lifetime, renewing within 30 days of expiry or when revoked/invalid/missing the
production CDP. A CA with less than 366 days remaining requires planned rotation.
The leaf CDP is exclusively:

```text
https://crl.net.scetrov.live/bullit-xrdp.crl
```

Every run generates a seven-day signed CRL, including all durable revoked
records, even if the leaf is unchanged. The issuer creates a **key-free ledger
backup**, signs it using the dedicated publisher's OpenSSH signature namespace
`xrdp-pki-state`, and uploads backup/signature before the CRL. There are seven
weekday backup slots on Habiki. CA keys, SSH keys, leaf keys and configuration
containing runtime paths are excluded from those archives.

Publication uses pinned-host-key SFTP to `xrdp-crl-publisher@10.229.10.2`. Habiki
admits that key only from `10.229.10.10`; its account is chrooted, forced to
internal SFTP and denied shell execution, forwarding and TTY. It cannot write
Caddy configuration or leave its artifact directory. The publisher identity is
root-only on Bullit and loaded as a systemd credential. Never place the CA key
on Habiki to simplify distribution.

After SFTP succeeds, the issuer retrieves the exact CRL over trusted HTTPS with
no proxy/redirect/authentication fallback, requiring byte-for-byte agreement.
Only then may it atomically replace `/var/lib/xrdp-tls/current`. The key is
`0640 root:xrdp`; current and preceding generations are retained. The parent
must remain `0750 root:xrdp` even on a no-op renewal: systemd's directory ownership
must agree with that group. Publication failure leaves the previous pair intact.
A listener-only restart is queued after replacement; sesman is never restarted.
Verify the queued listener restart, not merely the preparation unit's success.

**Availability:** startup requires Habiki publication to succeed. Ongoing desktop
sessions are not intentionally terminated when a later refresh fails. Windows
may cache a CRL until its seven-day `nextUpdate`; daily publication does not
promise immediate revocation for clients retaining a valid cached CRL. Clients
outside the local network cannot retrieve this private CDP.

## Habiki endpoint, DNS and monitoring

Caddy reuses its existing public wildcard TLS certificate and ports. Only actual
LAN peers (`10.229.0.0/16`) and exact loopback addresses can GET/HEAD the exact
CRL path. Forwarding headers confer no access. Other paths/methods return 404,
nonlocal peers 403, and HTTP 404 without redirect/fallback. There is no Authentik
redirect or download authentication: this is public signed validation data, not
an authenticated application. The shared alias maps to `10.229.10.2`; both
Fyne and Habiki Blocky resolvers must receive it through `local-networking.nix`.

`xrdp-crl-monitor` runs every five minutes as an unprivileged account. It verifies
the CRL signature/validity and the newest ledger archive's SSH signature, then
atomically writes Alloy textfile metrics in `/var/lib/xrdp-crl-metrics`. The
monitor has read-only group access to the key-free backups, not any signing key.
Alloy forwards metrics and journal/access logs to central observability.
Prometheus scrapes the same collector and a blackbox HTTPS probe. Rules cover:

- endpoint failure;
- invalid/missing CRL, failed backup verification or monitor older than 15 minutes;
- CRL with less than 48 hours remaining, or backup older than 36 hours.

Use `xrdp_crl_valid`, `xrdp_crl_next_update_timestamp_seconds`,
`xrdp_crl_backup_timestamp_seconds` and `xrdp_crl_check_timestamp_seconds`.
Rule configuration/evaluation is not proof of external notification delivery.

## Targeted deployment

The provisioning helper creates/reuses a dedicated publisher key in Vault and
writes only its public half into the NixOS source. It never persists plaintext
private material in the repository. Use the existing Nixpkgs PyYAML tool
already used by Ansible, not a new mutable pip install:

```sh
nix-shell -p 'python3.withPackages (p: [ p.pyyaml ])' \
  --run 'python3 scripts/provision_xrdp_publisher.py'
./scripts/play.sh --limit bullit,habiki,fyne --tags xrdp-pki --syntax-check
./scripts/play.sh --limit bullit,habiki,fyne --tags xrdp-pki
```

The ordered playbook copies only PKI/observability modules and required aliases,
updates no channels, invokes no OpenTofu, and runs no unrelated provisioning or
blanket container restarts. It activates complete host configurations, so review
drift first. Fyne uses only the existing DNS-only role. Scope and ordering
overrides are rejected by the wrapper. Check mode is not deployment verification.

**First initialization only:** the migration originally used
`-e xrdp_pki_initialize=true` after verifying no prior issuer database existed.
It imported the legacy leaf and revoked both diagnostic leaves whose private
keys had been destroyed. This flag is not a recovery shortcut. Further normal
runs require the existing issuer marker. The retired probe's runtime files may
be removed only after those records are imported and backed up.

## Revocation and recovery

For a compromised leaf, preserve the certificate, record revocation using the
issuer CLI's `revoke --revoke-cert <certificate>` action, then immediately run
`xrdp-tls-renew.service` through a targeted Ansible systemd task. The action uses
the same lock/database as renewal. If the current leaf was revoked, a replacement
is issued and activated only after successful CRL/backup publication. Verify the
HTTPS CRL and actual listener. Human/operator mutation must remain automated;
never hand-edit `index`, delete records or copy a previous CRL as silent fallback.

CLI common arguments (use the deployed immutable helper from the unit, or the
reviewed source through an Ansible script task):

```text
--state /var/lib/xrdp-ca --ca /run/agenix/xrdp_ca_cert
--ca-key /run/agenix/xrdp_ca_key --openssl <Nixpkgs OpenSSL executable>
```

Recovery backups are `/var/lib/xrdp-crl/upload/state-{0..6}.tar.gz` and adjacent
`.sig` files on Habiki, transferred before the corresponding CRL is published.
Fetch the newest consistent pair through approved Ansible automation. Verify
its signature with the publisher public key from the corresponding Git revision
and compare its signed CRL number/revocations with the latest known publication.
Do not blindly select by an untrusted filesystem timestamp after an incident.
Preserve old publisher public keys in Git when rotating the identity so older
backups remain verifiable. Habiki backups are not protection against simultaneous
loss/compromise of both hosts; keep repository/Vault recovery assets separately.

The CLI `restore` action requires an absent/empty destination, archive,
`--ssh-keygen <OpenSSH executable>` and `--publisher-public-key <trusted .pub>`.
It verifies the SSH signature before extraction, restricts members/size, rejects
links, checks the CA fingerprint/serial counter, verifies archived certificate
signatures and matches revoked records to the signed CRL. It restores no private
keys. Restore CA/publisher identities through Vault/agenix separately, then run
renewal and verify HTTPS and TLS before admitting clients. Never overwrite a
nonempty database automatically; preserve failed state for incident analysis.

## Verification and client acceptance

```sh
nix-shell -p openssl --run 'python3 -m unittest discover -s tests -p test_xrdp_tls.py -v'
nix-instantiate --eval --strict --expr 'import ./tests/xrdp-tls-eval.nix {}'
nix-instantiate --eval --strict --expr '(import ./tests/xrdp-pki-eval.nix {}).passed'
nix-build --no-out-link --expr '(import ./tests/xrdp-pki-eval.nix {}).caddySyntax'
pre-commit run --all-files
```

Check both normal and repeated systemd renewal, xrdp-user certificate/key access,
CRL/backup signatures and metrics. A real RDP-negotiated TLS handshake is required;
plain `openssl s_client -connect ...:3389` is not an adequate probe. Check wrong
hostname/untrusted CA rejection and legacy non-TLS rejection as well as success.

On the operator's Windows client, the preceding isolated HTTPS-only test passed:
`valid: accepted=True / NoError`, `revoked: accepted=False / Revoked`. That proves
this client's online chain engine can consume an HTTPS CDP, despite broader
compatibility guidance preferring HTTP. No HTTP fallback has been introduced.
It does not certify every Windows version or the production MSTSC login itself.

For the production leaf, use `certutil -verify -urlfetch <exported-server.cer>`
and reconnect using MSTSC with the same trusted CA and matching hostname/IP.
Do not mark Windows RDP acceptance complete until the operator confirms that the
revocation warning is gone. A reboot and external alert delivery require their
own verification; tests and active units do not substitute for either.
