# Verification — 2026-10-18

## Local gates and prerequisite repair

- Reproduced the stale Garage evaluation assertion before replacing its old
  tailnet listener binding check with the existing socket-peer restriction.
- `nix-instantiate --eval --strict --expr 'import ./src/roles/nixos/tests/garage-eval.nix {}'`
  passed. The operator approved host-side evaluation because Bubblewrap's cleared
  search path could not resolve `<nixpkgs>`. Documented this boundary and the
  function-application pitfall in `AGENTS.md`.
- `pre-commit run --all-files` passed, including Gitleaks, Nix formatting,
  Authentik checks and OpenTofu formatting through the required wrapper.
- The first deployment stopped before Ansible: `extract_secret` exited with
  SIGPIPE (141) when `awk` stopped reading a large vault before `printf` finished.
  A synthetic-only Bubblewrap reproduction confirmed pipeline statuses 141/0.
  With operator approval, added a real-wrapper regression test, observed failure
  before the fix, then changed the extractor to drain input while retaining only
  the first match. All 16 wrapper/secret-rendering tests passed, followed by the
  full pre-commit gates. The production retry successfully refreshed secrets.

## Deployment

- `scripts/play.sh --limit habiki --tags nixos`: 104 OK, 20 changed, 0 failed.
- Validated the full repository-built `/etc/caddy/caddy_config` on Habiki using
  its installed Caddy and existing systemd EnvironmentFiles: exit 0,
  `Valid configuration`. No separate hand-assembled config was activated.
- `scripts/play.sh --limit fyne,habiki --tags local-dns`: both hosts succeeded,
  0 failed. No deployment was widened to other hosts.

## Focused live smoke session

- The operator authorized a disposable bucket and bucket-scoped key. Provisioning,
  testing and cleanup ran through a one-off Ansible script task. Credentials stayed
  in memory, task output was protected with `no_log`, and only status lines were
  reported. The installed Garage 1.3.1 requires its v1 admin API; initial v2
  attempts created no resources. The v1 session completed successfully.
- Signed path-style requests with region `garage`: listing, PUT, byte-exact GET
  and DELETE passed through `s3.net.scetrov.live` with normal TLS verification.
- Signed multipart transfer passed: 5 MiB first part plus 1 MiB second part,
  completion, and byte-exact download of the resulting 6 MiB object.
- Signed access passed using loopback, Habiki's LAN source/address and its
  tailnet source/address. The unchanged tailnet hostname also passed signed
  listing and trusted TLS using the tailnet source/address.
- Invalid signatures and anonymous protected access were rejected by Garage.
- Caddy denied outside-allowlist sources `127.0.1.1` and `::1`, both with and
  without spoofed forwarded headers. `127.0.0.2` reached Garage authentication;
  the old tailnet hostname denied loopback access.
- All disposable objects, multipart uploads, the bucket and key were removed;
  cleanup reported zero errors. No credentials were recorded in the repository.
- Fyne and Habiki both resolved the new hostname to `10.229.10.2`. Each queried
  both internal DNS servers (`10.229.53.1` and `10.229.53.2`) successfully three
  times. An initial immediate post-restart query failed; subsequent explicit
  queries and repeated checks passed. Fyne's separate LAN-client HTTPS request
  passed certificate verification and reached Garage's authentication response.
- Garage S3, RPC and admin/metrics TCP listeners remained on `127.0.0.1`
  (3900, 3901, 3903). Caddy and Garage were active after deployment.

## Coverage limits

Tailnet-source signed tests originated on Habiki itself; no separate tailnet-only
client was available. Outside-allowlist tests used local IPv4/IPv6 source
addresses, not an external WAN vantage. No router, storage, credential rotation,
existing tailnet route or monitoring configuration was changed.
