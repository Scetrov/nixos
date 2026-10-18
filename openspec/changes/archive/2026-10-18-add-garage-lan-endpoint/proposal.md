## Why

Garage already serves tailnet backup clients, but LAN clients lack a stable HTTPS S3 endpoint. Address issue #31 by adding `s3.net.scetrov.live` without disrupting the existing tailnet endpoint.

## What Changes

- Add a Caddy S3 virtual host permitting peer addresses in `10.229.0.0/16`, `127.0.0.0/24` (the network represented by the requested `127.0.0.1/24`), and the existing IPv4 tailnet range `100.64.0.0/10`.
- Reuse the existing wildcard certificate and loopback Garage listener; reject other peers before proxying and retain S3 credential authentication.
- Add the LAN hostname to the existing declarative local DNS/hosts mapping. Tailnet-only clients continue using the unchanged tailnet hostname without needing LAN routing.
- Document path-style client configuration and verify signed object operations with a small smoke check.
- Extend the existing Garage evaluation test, correcting its stale tailnet binding assertion rather than creating another test framework.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `tailnet-s3-backup-target`: Scope the tailnet-only restriction to its existing hostname and add a complementary LAN/loopback/tailnet HTTPS endpoint, preserving storage, credentials and monitoring.

## Impact

Small changes to `caddy.nix`, `local-networking.nix`, `garage-eval.nix`, and `docs/garage-backup-target.md`. Reuse the Blocky/local-dns deployment path and existing DNS-01 certificate. No new dependencies, ports, secrets, Authentik configuration, storage migration, public DNS records, or new monitoring stack. Deployment is targeted to Habiki plus DNS-only convergence on Fyne and Habiki.
