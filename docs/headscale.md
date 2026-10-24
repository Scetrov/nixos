# Headscale control plane

## Ownership and network boundary

`src/roles/nixos/files/etc/nixos/modules/headscale.nix` runs the native
Headscale service on Habiki with SQLite WAL state in
`/var/lib/headscale/db.sqlite`. Preserve the service-owned database and controller
keys across restart, rebuild and disablement; a new empty database is not a
recovery of existing node registrations.

The advertised controller URL is `https://headscale.net.scetrov.live:8443`.
Caddy terminates the existing Cloudflare DNS-01 certificate and proxies to
`127.0.0.1:8090`. The router-facing 8443 listener must expose only this hostname's
controller protocol, not other Habiki sites. Do not add Authentik forward-auth:
Headscale owns node admission, and protocol clients cannot complete browser SSO.
Debug/metrics stay on `127.0.0.1:9091` and are not proxied publicly.

Cloudflare DDNS updates the IPv4 record every five minutes, unproxied; IPv6
publication is disabled. Its zone-scoped DNS-edit credential is supplied as an
agenix environment file for `cloudflare-ddns`, never copied into documentation
or Nix-store content. A usable public DNS answer, router TCP forwarding and
valid HTTPS are separate checks; local reachability alone proves none of them.
Embedded DERP was deferred; it is not part of the controller acceptance contract.

## Admission and private services

`/etc/headscale/policy.hujson` is declaratively generated with empty admin/project
groups and an empty ACL list: the baseline is default-deny. Add reviewed users,
tags and ACLs through configuration, not a broad allow-all repair. Explicit
node enrollment does not itself authorize arbitrary tailnet traffic.

The NixOS role's `headscale-enrolment.yml` enrolls Habiki only when it lacks a
running tailnet identity, using a one-hour preauth key under `no_log`. The
installed `headscale-enrolment` helper supports creating a user, creating a
reusable key for a numeric user ID (1h, 24h or 7d), and expiring a key. Use these
only through authorized operator/Ansible workflows; key creation prints a
credential, so capture it privately and never paste it into chat or logs.
Expiring an enrollment key is not proof of revocation of an already enrolled node;
review node/session policy separately.

MagicDNS uses `tailnet.net.scetrov.live`, leaves local DNS override disabled,
and maps `s3.tailnet.net.scetrov.live` to `100.64.0.1`. Preserve that existing
Garage client path; see [Garage](garage-backup-target.md). Tailnet transport
and application authorization remain separate boundaries.

## Deployment and checks

Use the targeted NixOS workflow after reviewing Habiki-wide configuration:

```sh
./scripts/play.sh --limit habiki --tags nixos
nix-instantiate --eval --strict --json --expr 'import ./src/roles/nixos/tests/headscale-eval.nix {}'
```

After an authorized rollout, verify `headscale`, `tailscaled` and
`cloudflare-ddns` units, persistent state permissions, loopback listeners,
the DDNS answer and external HTTPS on 8443. Verify an explicitly invited node
can enroll and an unauthorized node cannot; check the ACL baseline and that
other Caddy sites/debug endpoints cannot be reached through the forwarded port.
A restart/rebuild must preserve known nodes. Existing journals and private
Prometheus/Grafana health signals should expose controller/DDNS failures;
external reachability must be checked independently of loopback metrics.

For recovery, retain controller state/keys and restore them only through reviewed
automation with the service stopped. Reapply DNS/Caddy/policy and verify existing
nodes reconnect before issuing replacement enrollment credentials. Disablement
must remove dedicated ingress/DDNS/monitoring deliberately without deleting
node state or widening other service access. No off-host restore test is claimed
by this documentation consolidation.
