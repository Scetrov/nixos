## Context

Garage listens on `127.0.0.1:3900`; Caddy already proxies `s3.tailnet.net.scetrov.live` with a `remote_ip 100.64.0.0/10` restriction. That endpoint must remain unchanged. The `scetrov.live` DNS-01 certificate covers `*.net.scetrov.live`. Shared aliases live in `local-networking.nix` and feed the existing Blocky DNS deployment on Fyne and Habiki.

The existing `garage-eval.nix` still expects the old tailnet-only listener binding, despite Caddy now using a shared listener with peer-address filtering.

## Goals / Non-Goals

**Goals:** Add trusted HTTPS S3 access for `10.229.0.0/16`, `127.0.0.0/24`, and `100.64.0.0/10`, preserve backups, and keep the patch and verification small. Interpret the requested `127.0.0.1/24` as `127.0.0.0/24`.

**Non-Goals:** New identity flows, IPv6 access, virtual-host-style bucket names, new secrets or buckets, storage migration, public ingress, new proxy abstractions, or a new test harness.

## Decisions

### One additional virtual host, existing listener and certificate

Add `s3.net.scetrov.live` in `caddy.nix`, reuse `useACMEHost = "scetrov.live"`, reject peers outside the three allowed CIDRs with HTTP 403, then directly reverse-proxy to Garage. Use the actual socket peer (`remote_ip`), not forwarded headers. Do not add Authentik, URL rewriting, compression, upload limits, or custom proxy tuning without a demonstrated need. Caddy's ordinary HTTP upstream behavior preserves Host and signed request components.

Keep the existing tailnet virtual host and Headscale DNS record unchanged. A second small block is clearer than introducing a reusable abstraction for two sites with different access policies. Do not bind to a tailnet address that may not exist at Caddy startup, open Garage ports, or change the shared HTTPS firewall policy for unrelated services. TLS may remain reachable on the shared listener; denied peers must never reach the S3 upstream. All IPv6 sources, including `::1`, are outside the requested allowlist.

### Existing DNS and path-style S3

Map `s3.net.scetrov.live` to Habiki's `10.229.10.2` alongside existing aliases in `local-networking.nix`. Deploy that mapping to the existing DNS hosts; no public A/AAAA records or new DNS service. The new hostname requires LAN reachability; tailnet-only clients continue using `s3.tailnet.net.scetrov.live` at `100.64.0.1`. The new route also accepts tailnet peers if they can reach it; no subnet routing or split-DNS work is added. Habiki-local checks can resolve the hostname to loopback without disabling TLS verification.

Document endpoint `https://s3.net.scetrov.live`, region `garage`, and path-style addressing. Existing Garage bucket permissions and runtime-managed credentials apply to both endpoints. Reuse current Garage monitoring unchanged.

### Minimal verification

Extend only `garage-eval.nix`: replace the stale listener assertion with the actual tailnet peer restriction, assert the new allowlist/upstream/certificate and hostname mapping, and retain direct-port protections. Validate the rendered Caddy configuration using its existing validation mechanism. A single focused live smoke session covers DNS/TLS, signed listing and PUT/GET/DELETE, multipart transfer, unchanged tailnet access, and an outside-allowlist denial including spoofed forwarded headers. Use a disposable object in an authorized bucket and remove it afterward. Do not add a container/VM integration suite or performance benchmark.

## Risks / Trade-offs

- [A private source can still be untrusted] → Network admission is not bucket authorization; Garage still validates every S3 credential. This deliberately trusts the requested LAN range, not every RFC1918 address.
- [A future fronting proxy could hide the real peer] → This design assumes direct client connections to Caddy; do not trust forwarded headers or add a public fronting proxy.
- [Signed uploads behave differently through a proxy] → Preserve the request without rewrites; exercise signed multipart transfer before sign-off, adding tuning only if needed.
- [Tailnet-only clients cannot route to the LAN address] → Retain and document the working tailnet hostname rather than introducing routing changes.
- [Existing evaluation failure predates this change] → Reproduce and identify the stale binding assertion before replacing it; do not weaken unrelated assertions.

## Migration Plan

1. Make the small configuration/documentation patch and run the existing evaluation and configured pre-commit gates.
2. Deploy Habiki using the targeted NixOS automation (`--limit habiki --tags nixos`); converge DNS aliases on Fyne and Habiki using the existing `local-dns` tag.
3. Run the focused live smoke session. Record any unavailable external/IPv6 test vantage explicitly rather than claiming coverage.
4. Roll back by reverting the new virtual host and alias and redeploying the same targets. Existing Garage data, credentials and tailnet configuration remain untouched.

## Open Questions

None blocking. Confirm live routing and test-client availability during implementation; no additional network ranges are assumed.
