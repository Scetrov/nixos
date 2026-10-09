# Live deployment and acceptance — 2026-10-09

Status: **partial; blocked; not ready to archive**. Tasks 6.3–6.6 remain open.

## Identity plan and apply

- Reviewed the saved shared plan through `scripts/tofu.sh`: 7 additions, 6 updates, no deletions.
- Operator explicitly approved the shared updates: `scetrov` (Authentik user 9) added to the previously empty All Applications group; three existing OIDC providers' redirect-field representation updated without changing strict matching or URLs; branding CSS trailing newline; service catalog Forgejo link.
- Saved-plan apply succeeded: 7 added, 6 changed, 0 destroyed.
- Forgejo provider/application/owner group/access binding and Grafana dashboard (`svc-forgejo`) created. Generated OIDC outputs refreshed into encrypted `src/generated-secrets.yml`.
- Plan and captured output were kept in a mode-0700 temporary workspace under `/dev/shm`, not committed. No credential values are recorded here.

## Initial Habiki rollout

Ran `./scripts/play.sh --limit habiki --tags forgejo`.
The tool wait expired while Ansible continued; its final exit/recap was not captured.
Subsequent host inspection verified activation:

- Forgejo active/running, main process status 0; no failed systemd units.
- Backend bound to `127.0.0.1:3002`; dedicated SSH bound on TCP 2222.
- Administrative SSH remained reachable.
- Caddy, Blocky, Prometheus and Alloy active before and after activation.
- Local `/api/healthz` reported database/cache pass.
- Exactly one active native `authentik` authentication source (ID 1).
- No user accounts yet: owner first-login acceptance has **not** occurred.
- Only `forgejo.service` and `forgejo-secrets.service` matched Forgejo/Gitea units; no `forgejo-runner` account.
- `/var/lib/forgejo`: forgejo-owned, mode 0750; SQLite file: forgejo-owned, mode 0640.

HTTPS checks using curl `--resolve` (normal certificate verification, not insecure TLS):

| Path | Status |
| --- | --- |
| `/` | 200 |
| `/user/login` | 200 |
| `/metrics` | 404 |
| `/api/internal` | 404 |
| `/api/healthz` | 200 |
| `/api/v1/user` (anonymous) | 403 |

TLS verification succeeded. The health endpoint is currently reachable through
HTTPS; this contradicts the runbook's claim that it is not exposed. Decide whether
to deny it or correct the documentation before sign-off. Repository-content,
registration, password-bypass and non-owner OIDC denial are not yet accepted.

## Fyne DNS rollout

`./scripts/play.sh --limit fyne --tags local-dns` completed with exit 0:
`ok=5 changed=3 unreachable=0 failed=0`.
After the automated Blocky restart, querying `10.229.53.1` returned
`source.net.scetrov.live → 10.229.10.2`.

## DNS deployment blocker and attempted remediation

Habiki's `/etc/hosts` and deployed alias module contain the Forgejo alias, but
Blocky remained running since 2026-10-08 and querying `10.229.53.2` returned no A
answer. A hosts-only rebuild did not restart Blocky. Fyne's existing DNS-only
role explicitly restarts it and successfully serves the alias after rollout.

Operator approved fixing the consumer automation. Added a post-successful-switch
Blocky restart in `src/roles/nixos/tasks/rebuild.yml`, restricted to Habiki with
`forgejo_enabled`, excluding check mode. Updated `docs/forgejo.md` to describe it.
Ansible Forgejo syntax check passes. This remediation is **not live-verified**.

The repeat `./scripts/play.sh --limit habiki --tags forgejo` exited 2 before
NixOS rebuild, at `secrets : Generate Secret Files`
(`src/roles/secrets/tasks/main.yml:452`). Ansible reports non-zero command exits
with loop results intentionally censored by `no_log`. Recap:
`ok=31 changed=2 unreachable=0 failed=1 skipped=10`. The cause is now known:
the initial deploy's Ansible process kept running after its tool wait expired
and raced this run on the shared local `.age` working files. No secrets were
exposed; suppression was left intact.

## Second repeat deploy (clean) — successful

With no competing deployment processes, re-ran
`./scripts/play.sh --limit habiki --tags forgejo`: exit 0, `ok=77 changed=17
failed=0`. The new post-switch Blocky reload task executed, and **both** DNS
servers now answer `source.net.scetrov.live → 10.229.10.2`. Forgejo active
(main status 0), no failed units; Caddy/Prometheus/Alloy active. Still exactly
one active `authentik` authentication source after the second reconciliation.

## Runtime configuration and LAN denial checks (passed)

Live `app.ini` (read as root on Habiki, secrets redacted):

- `[service]` DISABLE_REGISTRATION=true, REQUIRE_SIGNIN_VIEW=true,
  ENABLE_INTERNAL_SIGNIN=false, ENABLE_BASIC_AUTHENTICATION=false,
  reverse-proxy auth off.
- `[actions]` ENABLED=false; `[repository]` FORCE_PRIVATE=true,
  DEFAULT_PRIVATE=private; `[server]` HTTP_ADDR=127.0.0.1:3002, SSH_PORT=2222,
  ROOT_URL=https://source.net.scetrov.live/, COOKIE_SECURE=true.
- `[security]` REVERSE_PROXY_LIMIT=1, REVERSE_PROXY_TRUSTED_PROXIES=127.0.0.1/32
  (spoofed X-Forwarded-For cannot influence origin checks).

Observed behavior:

| Check | Result |
| --- | --- |
| `http://10.229.10.2:3002` direct from LAN | connection timeout (loopback-only bind) |
| HTTPS via Caddy from a loopback-origin peer | 403 |
| `/` and `/user/login` over TLS | 200, certificate verification ok |
| `/metrics`, `/api/internal` through vhost | 404 |
| anonymous `/api/v1/repos`, `/api/v1/user` | 403 |
| `/user/sign_up` GET | page body: "Registration is disabled" |
| `/user/sign_up` POST (registration attempt) | 403 |

Operator accepted `/api/healthz` through the vhost (liveness ping only); docs
updated to state it is reachable from allowed sources while `/metrics` stays
denied. Non-owner OIDC denial and owner first login are not yet exercised
live. No Teleport/Headscale client checks performed yet.

## OIDC first-login failure and grant_types fix

First owner login attempt failed with "There was an error processing the
authorization request". Forgejo journal showed the redirect back with
`error=invalid_request` **from Authentik** (not a Forgejo config error).
Provider comparison: the working Grafana provider had a populated `grant_types`
list; the new Forgejo provider had `grant_types = []` — current authentik does
not populate a server-side default for newly created providers, and the
authorization endpoint rejects requests against a provider with no grant
Types. (Plan review could not see this: the field was `after_unknown` at plan
time.)

Fix in `terraform/authentik.tf`: explicit
`grant_types = ["authorization_code", "refresh_token"]` on the Forgejo
provider, with a comment explaining why. Plan showed only the intended
`grant_types` change plus the previously accepted cosmetic `redirect_uris`
field-normalization; applied via `scripts/tofu.sh` (0 added, 5 changed,
0 destroyed). Live provider verified: grant types present, strict callback
unchanged, client ID/secret unchanged.

## Live acceptance results (post grant_types fix)

Owner / access (all passed):

- Owner first login through authentik succeeded; Forgejo created user
  `scetrov` (id 1), `is_admin=1`, via the `authentik` OIDC source only.
- Exactly one auth source after every reconciliation (no duplicates).
- Auth source config verified live: `RequiredClaimName=groups`,
  `RequiredClaimValue="Forgejo Owners"`, `AdminGroup="Forgejo Owners"`,
  auto-discovery URL `application/o/forgejo`, scopes openid/profile/email.
  Non-owner denial is enforced by the signed group claim + the application
  policy binding; no local password form is rendered on the login page.
- Registration denied (page text + 403 on POST); anonymous `/api/v1/*` 403.
- `acceptance-test` repository exists, `is_private=1`, owner 1.
- SSH: clone **and** push of `ssh://git@source.net.scetrov.live:2222/scetrov/acceptance-test.git`
  with the registered acceptance key succeeded; host key RSA-4096 preserved
  across the two deployments (key mtime predates the second deploy).

Observability (all passed):

- Loki: `service=forgejo` / `unit=forgejo.service` streams present with host
  `habiki`; metric token values do not appear in shipped log lines.
- Prometheus: `up{job="forgejo"}=1` at `127.0.0.1:3002`, `gitea_build_info`
  version 16.0.5, `ForgejoServiceUnavailable` rule loaded (inactive).
- Grafana: `Forgejo Service` dashboard (uid `svc-forgejo`) present, 7 panels.

Actions / runner: `[actions] ENABLED=false`; no runner user or unit on Habiki
(re-checked after both deploys).

Existing services: caddy, blocky, prometheus, alloy, grafana, authentik
(podman server/worker/postgresql) all active; administrative SSH unchanged.

## HTTPS Git and API token access (passed)

A scoped token (provided by the operator in-session; the operator will
regenerate it post-acceptance) verified:

- `GET /api/v1/user` → 200, login `scetrov`, admin true.
- `GET /api/v1/repos/scetrov/acceptance-test` → private, branch `main`,
  `clone_url = https://source.net.scetrov.live/scetrov/acceptance-test.git`,
  `ssh_url = ssh://git@source.net.scetrov.live:2222/scetrov/acceptance-test.git`
  (correct advertised form, including port 2222).
- HTTPS `git ls-remote` and clone succeed; the clone contains the commit
  pushed over SSH (cross-protocol consistency).
- HTTPS `git push` succeeds (new commit visible on `main`).

## Open items / limitations
- Teleport/Headscale live client checks not performed: molasses (100.64.0.3)
  and molasses-windows (100.64.0.4) are offline in Headscale at acceptance
  time; no alternative VPN client available to the agent. LAN path is fully
  verified; VPN path is covered structurally (allowed source CIDRs include
  100.64.0.0/10 and both tailnet IPv6 ranges; same Caddy rules and nftables
  source-scoped 2222 rules serve both paths). No VPN routes or ACLs were
  changed.
- Denied-source live check: no external (non-private) test machine is
  reachable from this lab; closest equivalent performed is the loopback
  origin 403 through the shared vhost plus the spoofed-header fixture from
  task 6.2. Recorded as a documented limitation.

## Remaining acceptance

- HTTPS Git + API token access once a scoped token exists.
- ~~Headscale client path~~: operator accepted the documented limitation
  (both tailnet peers offline at acceptance time; VPN traffic is subject to the
  same Caddy virtual-host source rules and the same nftables source-scoped
  port-2222 rules as the verified LAN path). No VPN routes or ACLs were
  changed.
- ~~Acceptance artifacts~~: acceptance SSH key (id 1) deleted via API (204),
  `acceptance-test` repository deleted (204, now 404), local key material and
  token file remain in `/dev/shm` only and are to be discarded; the operator
  will regenerate the token.
