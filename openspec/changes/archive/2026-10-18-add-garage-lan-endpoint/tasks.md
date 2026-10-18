## 1. Add the complementary endpoint

- [x] 1.1 Add the `s3.net.scetrov.live` Caddy host using the existing wildcard certificate, a socket-peer allowlist of `10.229.0.0/16`, `127.0.0.0/24` and `100.64.0.0/10`, and direct proxying to `127.0.0.1:3900`; leave the tailnet host and Garage configuration unchanged.
- [x] 1.2 Add `s3.net.scetrov.live` to Habiki's `10.229.10.2` aliases in `local-networking.nix` and document both endpoints, region `garage`, path-style addressing and the LAN-routing limitation for the new hostname.

## 2. Validate with the existing tooling

- [x] 2.1 Reproduce the stale listener assertion in `garage-eval.nix`, replace it with the existing tailnet peer restriction, and add minimal assertions for the new host's allowlist, upstream, certificate and local alias; retain private-port protections and run the evaluation successfully.
- [x] 2.2 Validate the rendered Caddy configuration and run configured pre-commit gates; inspect the diff for unintended listener, credential or storage changes.

## 3. Deploy and verify

- [x] 3.1 Deploy Habiki through `scripts/play.sh --limit habiki --tags nixos`, then converge aliases through the existing DNS-only automation on Fyne and Habiki (`--limit fyne,habiki --tags local-dns`).
- [x] 3.2 Run one focused smoke session: internal DNS and trusted TLS; LAN, loopback and tailnet admission; signed authorized listing and PUT/GET/DELETE plus multipart transfer using disposable objects; invalid-credential rejection; outside-allowlist denial despite spoofed forwarded headers; unchanged tailnet endpoint and loopback Garage ports. Clean up test objects and record results or unavailable test vantage points without exposing credentials.
- [x] 3.3 Archive the completed OpenSpec change before any final commit or PR, and stage only the intended configuration, test, documentation and archived specification files after checking for secrets.
