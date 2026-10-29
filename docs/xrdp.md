# Bullit XRDP certificates

Bullit provides independent Plasma X11 remote-login sessions through XRDP. Its
existing desktop/session configuration is unchanged by TLS renewal.

## Trust and key custody

- The existing private CA is authoritative in encrypted `src/secrets.yml`
  (`xrdp_ca_cert`, `xrdp_ca_key`). Never regenerate it during deployment.
- The secrets role encrypts both values for the operator keys and Bullit's host
  key (`devenv` in `secrets.nix`), not Fyne or Habiki. Agenix exposes them root-only.
- Signing happens on Bullit. A root compromise can issue certificates trusted by
  clients of this CA. This is an accepted trade-off for unattended renewal; use
  this CA only for XRDP, not as a general-purpose trust anchor.
- Import **only the public CA certificate**, published at
  [`certs/bullit-xrdp-ca.crt`](certs/bullit-xrdp-ca.crt), into each client's trusted root store.
  On Windows, inspect its SHA-256 fingerprint out of band, then use Certificate
  Import Wizard → Trusted Root Certification Authorities (current user or local
  computer as appropriate). Never transfer the CA private key to clients.
- Connect using `bullit`, `bullit.net.scetrov.live`, or `10.229.10.10`; these are
  the certificate SANs and existing local DNS names. Clients must validate both
  the CA signature and the requested hostname/IP. Trusting a leaf fingerprint
  is not equivalent: that fingerprint changes on renewal.

## Renewal contract

`modules/xrdp-tls.nix` is imported only on Bullit. XRDP requires successful TLS
preparation after agenix before starting. TLS is mandatory: there is no automatic
self-signed fallback or downgrade to legacy RDP security.

The `xrdp-tls-renew.timer` checks daily (persistent, up to one hour jitter).
Preparation also runs when XRDP starts. It retains a valid certificate with more
than 30 days remaining; otherwise it generates a new RSA-3072 key and a 365-day
server-only leaf. Deployments do not unnecessarily rotate healthy certificates.
A CA with less than 366 days remaining causes an explicit failure requiring
operator CA rotation and renewed client enrollment.

The helper validates chain, server purpose, hostname/IP SANs, key pairing and
expiry before switching `/var/lib/xrdp-tls/current` atomically. The leaf key is
root:xrdp `0640`; the CA key remains root-only under `/run/agenix`. Only current
and preceding leaf generations are retained. Failure before publication leaves
the preceding pair untouched, never silently replaces it with self-signed TLS.
After publication a listener-only restart is queued; sesman is not restarted.
Verify the queued restart succeeded; a renewal-unit success alone is not proof
that the new certificate is being served.

## Targeted deployment

No new packages, channels, firewall ports, endpoints or DNS aliases are needed.
Use the existing automation, scoped to Bullit. The second command deliberately
starts at synchronization, skipping channel updates; run the syntax/evaluation
checks first because this also skips that role's preflight task.

```sh
nix-instantiate --eval --strict --expr 'import ./tests/xrdp-tls-eval.nix {}'
nix-shell -p openssl --run 'python3 -m unittest discover -s tests -p test_xrdp_tls.py -v'
./scripts/play.sh --limit bullit --tags nixos --syntax-check
./scripts/play.sh --limit bullit --tags secrets --skip-generated-refresh
./scripts/play.sh --limit bullit --tags nixos --skip-generated-refresh \
  --start-at-task 'Include NixOS sync tasks' --skip-tags user
```

This activates the complete Bullit host configuration; review the working tree
first. `--skip-tags user` avoids unrelated user credential/Syncthing provisioning. Never use an unscoped `play.sh` deployment for this change.

## Verification and recovery

```sh
systemctl status xrdp xrdp-tls-renew.timer
systemctl list-timers xrdp-tls-renew.timer
journalctl -u xrdp-tls-renew.service -u xrdp.service --since today
sudo openssl verify -purpose sslserver \
  -CAfile /run/agenix/xrdp_ca_cert -verify_hostname bullit.net.scetrov.live \
  /var/lib/xrdp-tls/current/cert.pem
sudo openssl x509 -in /var/lib/xrdp-tls/current/ca.pem -noout -fingerprint -sha256
```

The existing Alloy journal collector ships unit logs to Grafana/Loki; query
`{unit="xrdp-tls-renew.service"}` for renewal failures. A successful local check
is not proof of log ingestion, paging, a fresh boot, or client trust. Test a real
RDP client after importing the CA, and ensure its certificate warning disappears
without disabling certificate validation. The listener serves RDP-negotiated TLS,
so plain `openssl s_client -connect ...:3389` is not a sufficient live probe.

To retry after fixing a missing secret or failed renewal, use an approved targeted
Ansible systemd task to start `xrdp-tls-renew.service`, then verify the listener.
Preserve Vault CA material for recovery; do not delete `current` or generate a new
CA to suppress an error. The previous generation is retained for explicit,
validated operator recovery, not automatic fallback.

## Acceptance — 29 October 2026

- Targeted Bullit Ansible deployment completed, without channel updates.
  The initial activation exposed an invalid `agenix.service` requirement; this
  host uses activation-script decryption. Ordering now supports the actual
  agenix backends without requiring nonexistent units; a regression assertion
  rejects undeclared required services. XRDP was restored by the corrected deploy.
- XRDP and sesman are active, and the persistent daily timer is scheduled.
  The CA key is `0400 root:root`; the leaf key is `0640 root:xrdp`.
- Local RDP-negotiated TLS 1.3 verified the live CA-signed leaf for both DNS SANs
  and the IP SAN. It expires **29 October 2027 at 19:03:44 UTC**. Wrong hostname
  and absent CA trust were rejected.
- An Ansible-triggered repeat renewal was a no-op, preserving the listener PID.
- Five disposable-CA tests, Nix module evaluation, Ansible syntax validation and
  full pre-commit gates passed. No reboot, external desktop login, client trust
  enrollment, Grafana ingestion or alert delivery has been verified.

Public CA SHA-256 fingerprint (verify independently before client import):

```text
E8:A9:B7:96:DB:A9:B3:2A:DA:65:50:24:AB:10:A0:02:E7:2B:4B:FB:C2:6F:6E:DC:69:5A:53:FF:86:79:F2:C2
```
