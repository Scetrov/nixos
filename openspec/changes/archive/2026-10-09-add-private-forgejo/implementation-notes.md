# Implementation Notes — add-private-forgejo

Running log of verified facts, decisions, and measurements taken while implementing
this change. Facts here were verified against live sources on the dates noted.

## Current scope — Actions deferred by operator

The operator requested that Actions be removed from this design, then selected
**retain experimental code disabled** rather than delete it. Current scope is the
private Forgejo Git service, native Authentik OIDC, private DNS/HTTPS/SSH,
persistence, service observability and targeted deployment. Runner/job features
and their historical completion counts below no longer belong to this change.

- Updated proposal/design/specs/tasks consistently. Moved the old runner spec out
  of `specs/` to `deferred-actions.md` as historical future-work material. Removed
  runner deployment/registration, first-login gating, job tests and job alerts
  from active acceptance. OIDC first-login still requires live access validation.
- `scetrov.services.forgejo.runner.enable` is a separate default-off experimental
  option. Habiki explicitly sets it false. Forgejo Actions follows that option
  and is disabled in the current deployment. Merely enabling Forgejo no longer
  creates runner account/runtime/daemon/cleanup/timer/registration/egress state.
- Nix service-only evaluation passes on both firewall backends and asserts that
  Actions is false and all runner activation paths are absent. Earlier opt-in
  runner/egress fixture assertions are retained separately in the evaluation.
  Strict OpenSpec validation and whitespace checks pass. New task 4.1 is complete;
  revised progress is **14/27**, not comparable to the historical 18/32 scope.
- Before deferral, the operator selected a rootless Docker experiment. The
  channel's Docker 29.8.1 was fetched through Nix's signed/hash-checked store.
  A unique transient delegated user unit, socket and temporary data/exec/config
  paths reported rootless/systemd cgroup v2 and enforced 2 CPUs/2 GiB with the
  pinned Alpine image. This is a direct runtime probe, not Forgejo E2E acceptance
  or a production version/security-age approval.
- Added opt-in `FORGEJO_DOCKER_TEST_BINARY` fixture support. The Docker fixture
  temporarily allows host-loopback access solely to its disposable HTTP server;
  that is not a production policy. Action cache now uses a disposable
  `XDG_CACHE_HOME`. The acceptance run was interrupted at scope change; the exact
  unittest process exited, transient Docker unit is absent and its disposable
  storage was removed. No E2E Docker compatibility claimed or further Actions
  tests pursued. Experimental adapter remains unaccepted.
- Nothing deployed, newly staged, committed or archived this session. The
  pre-existing index still contains the old added runner-spec path until final
  staging; working-tree artifacts reflect the reduced scope.

All runner decisions, blockers and checkboxes described below are historical.

## 1.1 NixOS module APIs and versions (verified 2026-10-08)

Verified against the NixOS 26.05 channel (inventory `nixos_current_version: 26.05`),
release `nixos-26.05.11576.7c8764b7c7b0` (released 2026-10-08 09:56 UTC, channel page
hash-verified: `options.json.br` sha256 `b5f87faf4569…`, `packages.json.br`
`2e4242d05f9d…`, `nixexprs.tar.xz` `22d3d6d4973e…` — all match the published
releases.nixos.org index).

### Modules (present in 26.05 channel)

- `services.forgejo` (`nixos/modules/services/misc/forgejo.nix`):
  - `package` defaults to `pkgs.forgejo-lts`; free-form `settings` (app.ini sections)
    including `server.{ROOT_URL,DOMAIN,HTTP_ADDR,HTTP_PORT,SSH_PORT,DISABLE_SSH}`,
    `session.COOKIE_SECURE`, `log.{LEVEL,ROOT_PATH}`.
  - `database.type = "sqlite3"` (default), `database.path` default
    `${stateDir}/data/forgejo.db`, `stateDir` default `/var/lib/forgejo`,
    `repositoryRoot` default `${stateDir}/repositories` → persistent.
  - `secrets.<section>.<KEY> = <path>` maps to systemd `LoadCredential` +
    Forgejo `environment-to-ini` (env `FORGEJO__<SECTION>__<KEY>__FILE`). Module
    already wires `security.SECRET_KEY`, `security.INTERNAL_TOKEN`,
    `oauth2.JWT_SECRET` from `${customDir}/conf/*` files.
  - Built-in SSH: `server.DISABLE_SSH` (default false) + `server.SSH_PORT`
    (clone-URL port). Note: the module does not yet open a firewall port for the
    SSH listener — repository module must do so for 2222.
  - `settings.actions.ENABLED`, `settings.metrics.ENABLED` with
    `secrets.metrics.TOKEN` are supported (used by `nixosTests.forgejo`).
  - `settings.service.DISABLE_REGISTRATION` supported.
  - Module creates service user `forgejo`, runs via systemd; unit runs
    `environment-to-ini` on start.
- `services.gitea-actions-runner`
  (`nixos/modules/services/continuous-integration/gitea-actions-runner.nix`):
  - `package` defaults to `pkgs.gitea-actions-runner`; **must be set to
    `pkgs.forgejo-runner`** for Forgejo (as done in `nixosTests.forgejo`).
  - `instances.<name>.{enable,name,url,labels,token,tokenFile,settings,hostPackages}`.
  - `tokenFile` = env file with `TOKEN=`; module re-registers automatically when
    token or labels change (`.token-hash`/`.labels` in state dir) — supports
    controlled rotation; otherwise preserves existing registration across rebuilds.
  - Runs with `DynamicUser = true`, `User = "gitea-runner"`,
    `StateDirectory = gitea-runner`, working dir `/var/lib/gitea-runner/<name>`.
    NOTE: not the dedicated non-administrative account the design wants — a dedicated
    `users.users.forgejo-runner` + override, or a repository wrapper unit, is needed
    for task 4.1 (module hardcodes `User = "gitea-runner"`; DynamicUser with a
    reserved static name is acceptable: `gitea-runner` is a non-administrative
    unprivileged account, no shell, system user).
  - Container runtime: docker labels (`<label>:docker://image`) work with
    `virtualisation.podman.enable` via `DOCKER_HOST=unix:///run/podman/podman.sock`
    **only when podman is rootful** (`/run/podman/podman.sock`). Rootless per-user
    podman uses `$XDG_RUNTIME_DIR/podman.sock` — the module does not support a
    rootless socket directly. Task 4.x must decide: rootful podman with
    per-job `--user` restrictions vs dedicated rootless runtime. See 1.4.
  - `instance.settings` is free-form YAML passed to the runner's config file
    (concurrency, per-runtime limits configurable there: `concurrency`,
    `container.dry-run`, cpu/memory settings per act-runner runner config).

### Package versions (26.05 channel, 2026-10-08)

- `pkgs.forgejo-lts` = **15.0.9** (LTS; module default).
- `pkgs.forgejo` = **16.0.5** (latest stable).
- `pkgs.forgejo-runner` = **13.2.0**.
- `pkgs.forgejo-cli` also present (useful for identity reconciliation, task 3.5).
- Upstream release dates (Codeberg/Gitea API, 2026-10-08):
  - forgejo v16.0.5 2026-09-17, v15.0.9 2026-09-17, v16.0.4 2026-09-10, v15.0.8 2026-09-10.
  - runner v13.2.0 2026-09-18, v13.1.0 2026-08-31.
- All are ≥ 7 days old (21 days) → 7x7 rule satisfied for both LTS and stable;
  no open advisories identified for these exact versions (advisories API not
  machine-readable at fetch time; versions match current upstream stable/LTS
  latest).
- Integrity: channel tarball hashes verified against releases.nixos.org index;
  package fetchers (`fetchFromCodeberg`/`fetchFromGitea`) carry sha256 hashes in
  nixpkgs sources (`forgejo` 16.0.5 `sha256-Ci6QuRNZ4miU…`, runner 13.2.0
  `sha256-2P3lWzC3yxcy…`), enforced at build time by Nix.

### Selection decision (pending 1.3/1.4 host checks)

- Server: `pkgs.forgejo` **16.0.5 stable** — confirmed with the operator
  2026-10-08 (latest stable preferred over LTS 15.0.9). Module default is
  forgejo-lts, so the repository module must set `package = pkgs.forgejo`.
- Runner: `pkgs.forgejo-runner` 13.2.0 via `services.gitea-actions-runner`.
- Compatibility: forgejo runner v13 is the supported runner line for Forgejo
  15.x/16.x server instances (v13 targets Forgejo ≥ 11).

## 1.3 Habiki listeners, capacity, VPN sources (inspected live 2026-10-08)

Host: habiki 10.229.10.2/16 + 10.229.53.2/16 (Blocky), tailscale0 100.64.0.1/32
(tailnet subnet 100.64.0.0/10; peers: molasses 100.64.0.3, molasses-windows
100.64.0.4). 4 vCPUs, 15 GiB RAM (~7.6 GiB available), 3.6 TiB NVMe (25% used),
NixOS 26.05.

### Observed TCP listeners (relevant subset)

- 443/8443 shared Caddy HTTPS listener (`*:*`), plus 80/443/8443 firewall rules
  in `caddy.nix`.
- Habiki LAN IP bound: 3000, 5432, 8123 (HA), 5433, 33593 (unidentified, pre-existing).
- Loopback: 2019 (authentik admin UI? — pre-existing), 3003/3005 (grafana), 3100
  (loki), 3200 (tempo), 8080 (mimir), 9000 (authentik outpost), 9090 (prometheus),
  9177, 9184/9185/9188 (exporters), 8787 (hermes), 3900/3901/3903 (garage),
  4000 (blocky), 4040 (pyroscope), 12345 (alloy), 18080 (oncall), 8000 (mcp),
  8081/8082 (dependency-track), 9200-err not present, 12345.
- **3000 is already taken on 10.229.10.2 by immich-api** (33593 = immich) —
  the Forgejo module default `HTTP_PORT 3000` MUST be overridden; bind the
  Forgejo HTTP listener to `127.0.0.1:3002` (`HTTP_ADDR = "127.0.0.1"`).
  3002 is free on loopback (checked against full `ss` output).
- Free loopback ports chosen: **3002** (Forgejo HTTP) and **3004** reserved unused
  (metrics shares 3002 under `/metrics` with bearer token when supported).
  Decision: single Forgejo HTTP listener on `127.0.0.1:3002`; metrics path
  `/metrics` served by the same listener protected by
  `settings.metrics.ENABLED = true` + `secrets.metrics.TOKEN` (Forgejo supports
  token-protected metrics on the main listener; no auxiliary port needed).

### Private access rules (chosen)

- Caddy: new `source.net.scetrov.live` virtual host on existing scetrov.live
  wildcard cert; restrict with `@notPrivate not remote_ip 10.229.0.0/16 not
  remote_ip 100.64.0.0/10 not remote_ip fd0b:281e:d657:3ca1::/64 not remote_ip
  fd7a:115c:a1e0::/48` → `respond 403` (LAN + LAN-ULA + Headscale tailnet,
  same pattern as `s3.tailnet.net.scetrov.live`). Deny internal routes: `/api/internal/*`
  and `/metrics` via `handle` → 404/403 before the reverse_proxy, so Prometheus
  scrapes the loopback port directly.
- SSH 2222 (Forgejo built-in SSH): nftables firewall is enabled
  (local-networking.nix). NixOS `allowedTCPPorts` has no per-source CIDR, so
  use `networking.firewall.extraCommands` to add nftables accept rules for
  tcp dport 2222 from `10.229.0.0/16` and `100.64.0.0/10` plus tailnet IPv6
  `fd7a:115c:a1e0::/48` (observed tailscale0 `fd7a:115c:a1e0::1/128`).
  Everything else default-dropped. Admin SSH 22
  unchanged; verify at deploy that 22 stays reachable and 2222 is dropped for
  non-private sources (IPv4 and IPv6).

### Observability (existing, reused — task 5)

- Alloy `loki.source.journal` ships all journal units to central Loki with
  `job=systemd-journal`, `host=habiki`, `unit=<unit>`; a `service` label is
  derived by regex relabel rules per service family (e.g. `(oncall-prepare-env|...)`
  → `service=oncall`). **Action for 5.1:** add a relabel rule mapping
  `(forgejo|gitea-runner-forgejo).*\.service` → `service=forgejo` (and a runner
  variant) so both appear under stable service labels in Loki.
- Prometheus static configs in `prometheus.nix` (`127.0.0.1:<port>` jobs). **
  Action for 5.2:** add job `forgejo` → `127.0.0.1:3002/metrics` with bearer
  token auth (agenix `forgejo_metrics_token`), plus existing node_exporter for
  host health; runner health via systemd unit state exporter or journal-based
  Grafana query.

### VPN source observations

- Headscale: clients sit on 100.64.0.0/10 (tailscale0 on Habiki is
  100.64.0.1/32; observed peers 100.64.0.3/.4). Caddy `remote_ip` sees
  100.64.0.x for tailnet clients.
- Teleport: no Teleport process/config found in this repository (searched
  src/terraform/docs); owner confirms Teleport clients reach LAN IPs — they
  arrive on the 10.229.0.0/16 LAN path (source IPs in 10.229.0.0/16), same as
  observed LAN sources (10.229.0.1 gateway, 10.229.5.x clients). **Decision:**
  `10.229.0.0/16` + `100.64.0.0/10` covers LAN, Teleport-on-LAN, and Headscale
  tailnet; verified at acceptance (task 6.4/6.5) by actual client checks.
- No new Headscale routes/ACLs required (owner confirmation + observed config).

## 1.4 Runner runtime compatibility spike (verified 2026-10-08)

Selected runtime: **dedicated rootless Podman 5.8.7 (crun + netavark/pasta,
aardvark-dns)** serving the Docker-compatible API via `podman system service
--time 0 unix://$XDG_RUNTIME_DIR/podman.sock`, under a dedicated
non-administrative `forgejo-runner` user on Habiki. `DOCKER_HOST` is pointed
at that rootless socket by the runner unit; Habiki's shared rootful runtime is
NOT used.

Proven locally on bullit (NixOS 26.05, podman 5.8.7 — same versions as
Habiki):

- Rootless `podman run --cpus 2 --memory 2g` works (crun cgroup v2 limits).
- `podman system service` Docker API: `_ping`, `version`, container
  **create/start/logs/delete** with `HostConfig.NanoCpus=2000000000` and
  `Memory=2147483648` all succeed — the exact API surface the runner uses.
  (Container output `CONTAINER_OK`.)
- Default bridge network DNS works from rootless containers: host
  nameservers are forwarded (10.229.53.1/2, 1.1.1.1, 8.8.8.8 via
  aardvark), public name resolution and outbound HTTPS verified
  (registry-1.docker.io resolved; /v2/ answered). `pasta` is the rootless
  network cmd; no slirp4netns dependency.
- **Forgejo Runner v13.2.0** binary (official `forgejo-runner-13.2.0-
  linux-amd64`, sha256 `fadaec897f…` verified against the published
  `.sha256`) runs and exposes `register` with `--instance/--token/--labels/
  --no-interactive`, matching the NixOS module's registration flow.

Limit enforcement decision: the runner's config `container` settings
(`CPUSET`/`CPUS`, `MEMORY_LIMIT`) are not all supported by the runner; the
enforced path is the runner `config` `concurrency: 1` plus per-container
limits passed by the runner itself. Verification approach: acceptance job
reads its own cgroup `cpu.max`/`memory.max` (task 4.5).

Remaining E2E (real Forgejo checkout → build → artifact) will be executed on
Habiki during tasks 4.5/6.4 with the acceptance workflow against the real
loopback Forgejo endpoint; the half that was locally unprovable without a
Forgejo server (git checkout + artifact upload) is covered there.

## 2.1 / 2.2 / 2.3 Identity + generated-secret pipeline (code done 2026-10-08)

OpenTofu (`terraform/`):
- `variables.tf`: added non-sensitive `forgejo_owner_username` (default "scetrov").
- `authentik.tf`:
  - `random_id.forgejo_client_id`, `random_password.forgejo_client_secret`.
  - `data.authentik_user.forgejo_owner` (from `var.forgejo_owner_username`).
  - `authentik_provider_oauth2.forgejo` — public client, strict redirect
    `https://source.net.scetrov.live/user/oauth2/authentik/callback`, property
    mappings openid+profile+email+groups.
  - `authentik_application.forgejo`.
  - `authentik_group.forgejo_owners` = [data.authentik_user.forgejo_owner].
  - `authentik_policy_binding.forgejo_access` (app → forgejo_owners).
- `grafana.tf`: outputs `forgejo_oidc_client_id` / `forgejo_oidc_client_secret`
  (sensitive).

Forgejo callback path verified against v16.0.5 source:
`routers/web/web.go` line 883 `m.Get("/{provider}/callback", ...)` under the
`/user/oauth2` group → `/user/oauth2/authentik/callback`. Confirms the strict
redirect URI.

`scripts/tofu.sh`:
- jq refresh now also requires and writes `forgejo_oidc_client_id` and
  `forgejo_oidc_client_secret` into `src/generated-secrets.yml` (fail-fast on
  missing via the shared `required()` helper).

`src/roles/secrets/tasks/main.yml`:
- Forgejo OIDC values validated (non-empty / non-null / non-placeholder) BEFORE
  agenix rendering, but scoped `when: forgejo_enabled | default(false)` so the
  long-standing Grafana/DTrack assertions stay host-unconditional while Forgejo
  (a new per-host service) only fails on hosts that actually deploy it, before
  the generated values exist.
- `age_secrets` now includes `forgejo_oidc_client_id` / `forgejo_oidc_client_secret`
  as bare-value `.age` files (Forgejo `secrets.oauth2.*` uses systemd
  LoadCredential, reading raw file contents → `FORGEJO__oauth2__CLIENT_ID__FILE`).
- `secrets.nix`: added `forgejo_oidc_client_id.age` / `forgejo_oidc_client_secret.age`
  publicKeys = users ++ systems.

Validation done via `scripts/tofu.sh -- validate` (config valid) and
`scripts/tofu.sh -- plan` (6 forgejo resources planned for creation; owner user
id=9 resolved). See CAVEAT below.

### CAVEAT — pre-existing shared-plan apply blocker (NOT caused by this change)
`scripts/tofu.sh -- plan` returns exit 1 with 6 errors, all on PRE-EXISTING
resources unrelated to Forgejo (grafana, homeassistant, homeassistant-oidc,
dependency_track, all_applications, brand) failing to READ via the authentik
provider with `HTTP Error 'no value given for required property pbm_uuid'`.
Plan still prints `Plan: 6 to add, 5 to change, 0 to destroy`. These read errors
must be resolved before `tofu.sh apply` can provision the Forgejo resources
(task 2.1 apply / task 6.3). Investigating the pbm_uuid provider error is a
separate prerequisite; flagged to the operator.

### Compatibility remediation (verified 2026-10-08)

Operator selected a compatible-provider downgrade rather than a shared server
upgrade. Reproduced the six `pbm_uuid` errors with provider 2026.8.0, then
exact-pinned `terraform/main.tf` to **2026.5.1**. Registry lists 2026.5.0,
2026.5.1, and 2026.5.2; upstream release API dates 2026.5.1 to August 10 and
2026.5.2 to October 2 (only six days old, deferred under the seven-day policy).
The 2026.5.1 go.mod selects SDK `v3.2026050.0-rc2`, whose Application decoder
requires no `pbm_uuid` (verified via proxy.golang.org archive). The 2026.5.2
SDK `v3.2026050.7` likewise removes this requirement, but is not yet eligible.

Re-ran `scripts/tofu.sh -- validate -no-color` and
`scripts/tofu.sh -- plan -no-color`: both exit 0, zero `pbm_uuid` errors.
Plan: **6 additions, 5 in-place changes, 0 destroys**. Existing changes affect
brand, All Applications group, and Grafana/Dependency Track/Home Assistant
OIDC providers; must review their field-level blast radius before task 6.3.
No apply or server restart performed. Provider download integrity is enforced
by OpenTofu's registry checksums and local gitignored lock file (repository
policy); version is exact-pinned despite wrapper `init -upgrade`.

Sources: registry.terraform.io/v1/providers/goauthentik/authentik/versions;
api.github.com/repos/goauthentik/terraform-provider-authentik/releases/tags/v2026.5.1
and v2026.5.2; tagged upstream go.mod; proxy.golang.org SDK zip.

## 3.1–3.4 Service and private access (implemented 2026-10-08)

- Added `modules/forgejo.nix`, enabled only in Habiki device configuration and
  inventory. SQLite/state/repositories and built-in Git SSH keys live under
  `/var/lib/forgejo`; HTTP binds only 127.0.0.1:3002. RSA-4096 host keys are
  generated by upstream `modules/ssh/ssh.go:GenKeyPair` and reused on restart.
- Caddy uses the existing wildcard certificate, native auth (no forward-auth),
  the four private source networks, and denies `/metrics` and `/api/internal`
  trees. Forgejo trusts forwarded addresses only from 127.0.0.1/32.
- **Correction to §1.3/handoff:** live `systemctl is-active firewall nftables`
  returned active/inactive; `iptables` exists, `nft` does not. The shared
  local-networking module does NOT enable nftables. SSH rules therefore use
  iptables/ip6tables on Habiki, with a conditional `extraInputRules` implementation
  for nftables hosts. TCP 2222 is never globally allowed; port 22 is untouched.
- Shared alias added. `play.sh --limit fyne --tags local-dns` copies only the
  local-networking module into an existing provisioned configuration, rebuilds
  that configuration, and restarts Blocky. It does not sync other modules,
  channels, secrets, or device configuration or refresh OpenTofu outputs.
  NixOS activation still evaluates the host's existing configuration; it is not
  a promise that unrelated pre-existing drift cannot activate.
- `forgejo-eval.nix` validates service/state/settings, both firewall backends,
  Caddy trust/routes, and disabled service absence. Passed against local
  NixOS 26.05, Forgejo 16.0.5.
- Real Caddy 2.11.7 fixture verifies spoofed X-Forwarded-For/X-Real-IP cannot
  admit a denied peer (403); admitted fixture requests reach Git/API paths,
  but metrics/internal routes return 404. Only the test fixture adds loopback
  to the whitelist. No live certificates/secrets used.
- 13 Python tests pass, Ansible syntax and Fyne DNS-only task listing pass,
  shell syntax and git diff whitespace checks pass. No live deploy performed.
  Runtime persistence remains task 3.6/6.6; OIDC and metrics credentials have
  not yet been wired into the service.

### Task 3.5 investigation — protected OIDC CLI input

Forgejo v16.0.5 `admin auth add-oauth`/`update-oauth` support idempotent CLI
reconciliation, but expose client secret only through `--secret VALUE`.
Tagged `cmd/admin_auth_oauth.go:oauthCLIFlags` defines no file/stdin/env source
for this flag. Passing an agenix secret that way risks process-argument
capture, contrary to the intended no-process-logging secret contract.
Unlike OAuth auth reconciliation, `forgejo-cli actions register` DOES offer
`--secret-file`/`--secret-stdin` in v16 docs, useful for task 4.2.

Need an agreed supported protected-input approach before 3.5 is complete;
do not write authentication-source database rows directly or relax secret
handling silently. A small reviewed package patch adding a file-backed OAuth
secret flag is one possible approach, but changes the vanilla-package decision
and entails rebuilding/maintaining the patch. Other protected interfaces
remain to be investigated. Owner-only verified-claim mapping, automatic OIDC
enrollment with closed local registration, and password-form bypass controls
also remain unimplemented/unverified. Both Basic password auth and internal
password-form signin are now disabled (`ENABLE_INTERNAL_SIGNIN = false`,
verified in tagged app.example.ini and included in evaluation assertions);
live bypass tests remain pending.

Follow-up alternatives investigation (operator requested): v16.0.5 generated
Swagger `templates/swagger/v1_json.tmpl` exposes no authentication-source
management endpoint. `/user/applications/oauth2` manages this forge's OAuth
applications, NOT external sign-in sources. Tagged `models/auth/source.go`
has database-backed sources with no auth.d/SourceFile native configuration
support; tagged OAuth CLI flags have no configured file/env sources. Current
published CLI docs likewise show only `--secret VALUE` for add/update-oauth.
No protected supported alternative was found in these interfaces. Shell
substitution or a secret environment variable expanded into `--secret` still
puts the value in argv; these are not fixes. Direct database edits, web-admin
CSRF/session scraping, and process-argument hiding hacks were not implemented.
**Operator decision — blocker resolved:** The operator explicitly accepts
OIDC client-secret exposure in the standard Forgejo CLI's runtime argv,
judging a maintained custom patch to be the greater risk. Use upstream
`add-oauth`/`update-oauth` with `--secret VALUE`; do not patch the package.
Read values from protected runtime files, never embed them in Nix/store
scripts, disable shell tracing, and suppress/redact captured command output
and errors (including subprocess exceptions that can include argv).
Process inspection or argument-capturing telemetry remains an accepted
residual risk; do not claim these controls eliminate it. Acceptance is limited
to this OIDC CLI limitation, not runner registration or other credentials
with file/stdin support. Updated design §6 records the exception. Task 3.5
is unblocked but remains incomplete pending implementation and validation.

### Task 3.5 implementation — completed locally

- `forgejo-reconcile.py` invokes only supported upstream auth list/add/update
  commands. Existing source ID is reused across repeats/rotation; duplicate
  names and unexpected source types fail closed. Updates retain intentional
  source disablement rather than undoing access revocation.
- The service loads agenix client ID/secret as systemd credentials, then runs
  reconciliation after upstream config rendering/migration and before web
  startup. Encrypted-file restart triggers handle rotation. No values enter
  Nix/store scripts; subprocess output/errors are captured and never emitted,
  including timeout exceptions. The runtime argv exception remains applicable.
- Source admission requires the signed `groups` claim to include `Forgejo
  Owners`; the same signed group maps administration. No local bootstrap user
  or password is needed. Auto-enrollment is explicitly enabled, email/account
  auto-linking disabled, legacy OpenID disabled, and local/password routes remain
  disabled. Tagged v16.0.5 OAuth callback permits auto-enrollment independently
  of `DISABLE_REGISTRATION`; this retains closed local registration.
- Five fixture tests pass, including actual Nixpkgs Forgejo 16.0.5 CLI + disposable
  SQLite + local OIDC discovery: first deployment, repeated update, client-secret
  rotation preserve a single source ID and enforce the intended claim mappings.
  Fixtures only read SQLite for verification; production never edits DB rows.
- Expanded Nix evaluation passes against 26.05 (invoke the function with `{}`,
  not just `--eval file`, which returns an unevaluated lambda). Browser OIDC
  admission/denial and live restart persistence remain tasks 6.4 and 3.6/6.6.

Sources: tagged v16.0.5 `custom/conf/app.example.ini`, `modules/ssh/ssh.go`,
`cmd/admin_auth_oauth.go`, `cmd/admin_auth.go`, `routers/web/auth/oauth.go`,
Nixpkgs `nixos/modules/services/misc/forgejo.nix`, and
forgejo.org/docs/v16.0/admin/command-line/.

### Task 3.6 local lifecycle validation

The real v16.0.5 fixture starts/stops the loopback web and built-in SSH servers,
creates a private initialized repository through the supported API with a
fixture-only user/token, and reruns migration/startup. Account/token access,
repository/README content, and SSH private-key bytes persist. Both listeners
close on stop while state remains. Nix evaluation separately verifies disabled
service/Caddy/firewall absence. This is local package lifecycle + declarative
evaluation, not a claim that a live NixOS rebuild was tested (still 6.6).
All 18 enabled Python tests pass; the Caddy fixture requires `CADDY_BIN` and was
skipped in the latest run. Six identity/lifecycle tests ran against the actual
Nixpkgs Forgejo binary. No live deployment occurred.

### Runner first-deploy ordering — decision required

Upstream `forgejo actions generate-runner-token --scope scetrov` calls the
internal endpoint whose `routers/private/actions.go:ParseScope` first calls
`user_model.GetUserByName`. It cannot register an owner-scoped runner before
that account exists. Current OIDC-only enrollment creates the owner at first
successful sign-in, not during authentication-source reconciliation. The
supported admin user-create CLI cannot assign an external login source/subject.
Do not silently create an unlinked local owner or widen to global registration.
**Resolved:** operator approved a documented first-login gate inside the single
 targeted command. The command waits after Forgejo/OIDC startup for the owner to
 sign in once, then continues registration; repeats skip the gate. Design §7
 records this decision. Task 6.1 still needs to implement the gate.

### Tasks 4.1–4.2 runner runtime/registration

- Dedicated `forgejo-runner` system account has no administrative groups,
  nologin shell, automatic subordinate UID/GID allocation, and declarative
  lingering. Runner-only user units provide the user bus/delegated cgroups for
  a dedicated rootless Podman API socket under `%t/forgejo-runner-runtime`.
  Its graph storage is separate from Habiki's shared rootful runtime.
- Runner-owned home/runtime/transient paths are separate from protected
  `/var/lib/forgejo-runner-control` (root-owned sibling, 0750, runner group).
  Root owns generated config/UUID/token files (0640, runner group). The runner
  cannot redirect privileged registration writes through a writable parent.
- Daemon requires the dedicated runtime and waits for a successful API `_ping`.
  It is guarded by the protected registration config. Missing registration
  does not start jobs. Execution labels are empty until task 4.3 configures
  verified ceilings and a digest-pinned image; cache endpoint is disabled.
- **Correction:** Nixpkgs `forgejo-cli` is the unrelated `fj` client (0.6.0),
  not the server registration CLI. The correct supported command shipped in
  Forgejo 16.0.5 is `forgejo forgejo-cli actions register --secret-stdin true`.
  No new `forgejo-cli` dependency is needed. Input is exactly 40 hexadecimal
  characters without a newline, supplied through captured subprocess stdin.
- Registration runs the supported CLI as the Forgejo account; no runner token
  enters argv. Client config uses v13 `server.connections.*.token_url` to read
  the protected token file. Ordinary reconciliation validates existing tokens
  using authenticated Connect `RunnerService/Declare` (not unauthenticated Ping)
  before updating. HTTP authorization rejection requires explicit `--recover`;
  outages fail closed rather than registering again.
- `--rotate` / `--recover` preserve the token's first 16 characters, from which
  upstream derives UUID, while changing its remaining 24. This updates the
  same registration. First-deploy token identity is persisted before touching
  server state so retries after partial failure cannot create new UUIDs.
- Real Forgejo fixture passes first/repeat/rotation, owner-only scope fields,
  API runner deletion, ordinary revoked-credential rejection, and explicit
  recovery. One active runner remains; upstream retains a soft-deleted history
  row with a tombstoned UUID (not a duplicate active runner). Initial SQLite
  `deleted` is NULL; corrected fixture predicates count NULL/zero as active.
  Production uses supported CLI/API exclusively, no database writes.
- Seven identity/lifecycle/registration fixture tests and expanded Nix
  evaluation pass. Actual lingering-user runtime startup/limits/jobs still
  require task 6.2/6.6 validation; nothing deployed on Habiki.

### Task 4.3 verification blocker — local exec does not use daemon configuration

Two bounded local rootless Podman job spikes timed out (120s / 30s). Captured
fixture diagnostics show `forgejo-runner --config config.json exec` selects the
unpinned default `node:20-bullseye` rather than the configured digest-pinned
`runner.labels` image and starts a cache handler despite `cache.enabled=false`.
Thus exec mode is not validating the intended daemon/container configuration;
it stalls pulling that unrelated default image. This is not evidence that the
production daemon ignores configuration or that Podman is incompatible. Runner
and test API subprocesses were terminated, temporary fixtures removed, and no
live services deployed. No production job image/labels or ceilings were enabled.
Do not mark 4.3 complete or assume limits from the earlier direct-Podman test.
Next: use an isolated actual Forgejo daemon-mode job fixture, or verify exec's
separate flag/config behavior, to measure cgroups/socket/mount restrictions.

### Task 4.3 daemon-mode fixture — exec blocker resolved

Added opt-in `scripts/tests/test_forgejo_runner_daemon.py`: actual Forgejo
16.0.5 web + SQLite on loopback, Forgejo Runner 13.2.0 daemon, supported scoped
registration and API-created workflows, and a separate rootless Podman graph/
run directory. All runtime cleanup uses explicit fixture `--root/--runroot`;
no live services/state or shared rootful runtime are touched.

Findings and verified correction:
- The daemon correctly selects the configured digest-pinned image and honors
  `cache.enabled=false`, unlike the earlier exec-mode spike.
- Initial jobs showed unlimited cgroup files. A direct isolated Podman control
  showed the same failure; this was not evidence of ignored runner resource
  options. Workstation defaults to `cgroupfs`, and tool processes inherited a
  private session DBus rather than the canonical user-manager bus.
- Explicit `--cgroup-manager=systemd` plus
  `DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus` produced
  `memory.max=2147483648`, `cpu.max=200000 100000` in both direct and daemon jobs.
  Runtime user unit now explicitly sets these choices (`%t/bus`) and Nix
  evaluation asserts them. No package patch or privileged fallback.
- Shared non-sensitive `forgejo-runner-config.json` is used by production
  registration and the daemon fixture. Fixture overrides only labels and test
  timeouts; tested CPU/memory/capability/socket/volume settings are identical.
  Production labels remain empty pending acceptance-image selection.
- Two independently eligible jobs succeed, with observed running count never
  exceeding one. The second requests `--privileged`, 8 CPUs and a bind of the
  protected control directory; those overrides do not grant privilege, exceed
  the CPU cap, or expose credentials. Both jobs verify CapEff=0,
  NoNewPrivs=1, no runtime socket, no host control file/mount and no inherited
  fixture host sentinel. The daemon has no listening TCP socket.
- A cold OCI archive import of a cached multiarch digest failed manifest
  integrity checks; switched to a direct immutable digest pull into the isolated
  graph. No tag fallback. Final graph contains only the requested image.
- Fixture uses pinned Alpine only for shell/cgroup checks, NOT a selected
  production CI image. No checkout/action/artifact/TLS acceptance is claimed.
  Generic JSON workflow rendering was rejected before jobs ran; fixture uses
  normal YAML and the actual job/run status API shapes.
- Latest full suite: **20 passed, 1 skipped** (Caddy requires `CADDY_BIN`),
  including this daemon integration. Expanded Nix evaluation and whitespace
  checks pass. Task 4.3 stays unchecked: transient cleanup remains unfinished.

Reproduce (Nixpkgs channel must match the selected versions):

```bash
FORGEJO_TEST_BINARY="$(nix-build '<nixpkgs>' -A forgejo --no-out-link)/bin/forgejo" \
FORGEJO_RUNNER_TEST_BINARY="$(nix-build '<nixpkgs>' -A forgejo-runner --no-out-link)/bin/forgejo-runner" \
FORGEJO_JOB_TEST_IMAGE=docker.io/library/alpine@sha256:14358309a308569c32bdc37e2e0e9694be33a9d99e68afb0f5ff33cc1f695dce \
python3 -m unittest scripts.tests.test_forgejo_runner_daemon -v
```

Requires a working systemd user manager, cgroup-v2 delegation, rootless Podman
and registry access. Actual Habiki dedicated-user-unit startup remains 6.2/6.6.

### Task 4.3 transient cleanup — completed locally

- Added descriptor-relative unprivileged cleanup of only runner `transient/workspace`
  and `transient/cache` contents. Root/child symlinks are rejected; job-created
  symlinks inside those directories are unlinked rather than followed. Registration,
  runtime image storage, Forgejo data, and other service paths are not pruned.
- Daemon startup cleans after runtime readiness; active containers left behind by
  a crashed daemon fail closed instead of deleting in-use workspaces.
- A dedicated weekly Sunday 04:00 user timer (up to 15 minutes jitter) stops the
  runner through systemd conflicts/order, allowing its configured graceful shutdown,
  then cleans and restarts it only on success. Failed cleanup leaves jobs stopped
  for deliberate recovery. This maintenance may interrupt a long-running job;
  it is not an idle-only scheduler. Cache service remains disabled.
- Two non-sensitive fixtures verify repeat cleanup, preservation of sibling
  Forgejo/control/runtime sentinels, nested symlink safety, and root/child symlink
  rejection. Nix evaluation verifies timer isolation, stop-before-clean ordering,
  startup cleanup and complete removal when disabled. Tests and whitespace pass.
- Task 4.3 complete at configuration/local-fixture level. Production execution
  labels still intentionally empty until 4.5; dedicated live user-unit validation
  remains 6.2/6.6. Nothing deployed or committed.

### Task 4.4 DNS, TLS and scoped egress — completed locally

- Operator selected coarse IP/port restrictions, explicitly accepting that other
  Caddy hostnames on shared `10.229.10.2:443` remain reachable. Design §7 records
  this boundary; no new egress proxy or VPN routing/ACL changes.
- Shared job template adds both Blocky DNS servers and a private Forgejo hosts
  entry. No insecure TLS option or host CA mount. A real rootless Alpine fixture
  verifies the hosts entry, public-name resolution through each Blocky instance,
  trusted wildcard HTTPS to the Forgejo hostname and public dependency HTTPS,
  and rejection when the certificate is addressed by its invalid IP hostname.
  Existing Caddy serves this wildcard before deployment; this proves transport,
  NOT Forgejo application, OIDC, checkout, or artifact readiness.
- Dedicated UID OUTPUT rules allow DNS TCP/UDP 53 only to `10.229.53.1/2`,
  `10.229.10.2:443`, and public TCP 80/443. Other private, loopback, link-local,
  multicast destinations and other ports are rejected. Rules cover rootless
  networking helpers running as this host user; they do not change other users.
- Isolated `sudo unshare --net` packet fixtures use the evaluated production
  iptables/ip6tables and nft rules, substituting only fixture owner UID. Both
  backends verify allowed/denied TCP IPv4/IPv6, UDP DNS, unaffected control/root
  traffic, repeated install/removal, and restored access after removal. No host
  firewall rules or interfaces were touched. This is not yet a live Habiki
  dedicated-runner-user/container egress test (still 6.6).
- Root-owned system readiness marker is published after the host firewall;
  daemon startup waits for it because user-manager ordering cannot depend on
  system-manager units. Disabling the module removes rules/readiness service.
- Full opt-in fixture suite now **25 passed, no skips**, including Caddy, actual
  daemon jobs with the updated template, DNS/TLS, both packet backends, and
  cleanup tests. Production execution labels remain disabled until 4.5.

Reproduce new probes:

```bash
FORGEJO_JOB_TEST_IMAGE=docker.io/library/alpine@sha256:14358309a308569c32bdc37e2e0e9694be33a9d99e68afb0f5ff33cc1f695dce \
python3 -m unittest scripts.tests.test_forgejo_job_connectivity -v
nix-shell -p nftables --run 'FORGEJO_EGRESS_TEST=1 python3 -m unittest scripts.tests.test_forgejo_runner_egress -v'
```

Packet fixtures require noninteractive sudo and existing iptables/ip6tables,
`ip`, `unshare`, and `setpriv`; all privileged changes remain inside the new
network namespace. Nothing deployed, committed or archived.

### Task 4.5 experimental acceptance — paused on fixture error

- Added non-sensitive example with two queued Node test/build/artifact jobs,
  commit-pinned checkout and Forgejo artifact action URLs, and digest-pinned
  job image. No deployment secrets. Examples are explicitly experimental;
  production runner labels remain empty and task 4.5 remains unchecked.
- Upstream queries establish latest Node 24 LTS = 24.21.0 (September 7).
  Official current bookworm tag rebuilt October 6, only two days old. Historical
  docker-library/repo-info commit `e5b5c696bc7353d0bf3eff9f70224a1c9daae40b`
  records the September 19 manifest
  `sha256:64af3819f9275802414d7cdc38c27e9d82bd564dec4d4da87d008255d36c63b4`.
  Its pull has not completed; Podman registry integrity/actual Node version and
  newer base-image security-update classification remain pending.
- Checkout v7.0.1 commit `3d3c42e5aac5ba805825da76410c181273ba90b1`
  (July 17) declares node24; Forgejo upload-artifact v5 commit
  `cb8afe72b42edc798abfb8fcb556cf660d894245` (December 29, 2025) declares node20.
  The v16 docs demonstrate patched v4; the newer fork must be fixture-tested.
- `FORGEJO_ACCEPTANCE_TEST=1` selects the experimental workflow in the existing
  real-daemon fixture, with a container-reachable advertised root URL. This
  test uses disposable HTTP, not a live HTTPS Forgejo acceptance claim.
- Reproduction stopped at the **90-second image-pull timeout**, before any web
  or runner subprocess/job. This establishes neither runner nor action
  incompatibility. Error cleanup subsequently hit PermissionError on subordinate
  UID-owned Debian apt image files; existing cleanup removes containers/networks
  but does not remove image storage before Python tempfile cleanup.
- Disposed of only that exact fixture graph via rootless `podman unshare`; its
  overlay directory had a Podman namespace bind mount, explicitly unmounted
  before final removal. No shared runtime/live data affected. Pause for guidance
  on bounded retry with complete fixture image cleanup. Previous full suite was
  25 passing; the new optional acceptance branch currently fails.

### Task 4.5 resume — pull resolved, action-copy blocker reproduced

- Increased only the immutable image-pull timeout to 600 seconds. The actual
  acceptance attempt reached daemon jobs; the complete failed attempt took 147
  seconds. Registry digest pull succeeded, direct cgroup limits passed, and job
  diagnostics report Node.js **24.21.0**. This does not settle the pending newer
  base-image security classification or validate checkout/artifact compatibility.
- First job failed **before the checkout action executed**. Forgejo Runner
  13.2.0's Docker copy through rootless Podman 5.8.7 returns:
  `statat var/run/act/actions/.../.git: path escapes from parent`.
  The later `MODULE_NOT_FOUND` is a consequence of the failed copy, not evidence
  of a Node/action-version incompatibility. Artifact upload did not run; the
  second job was still waiting when the workflow reported failure.
- The action clone cache used the workstation's existing `~/.cache/act`; the
  fixture does not yet isolate that cache. Investigate whether cache layout or
  Podman's archive extraction causes the copy error before choosing a runtime
  fallback. Do not claim rootless Podman end-to-end acceptance or enable labels.
- Corrected fixture cleanup: `podman network rm --all` is unsupported (exit 125)
  and previously ignored. Container removal releases rootless networks; graph
  deletion removes their definitions. Cleanup now checks container/image removal
  and deletes only the exact fixture graph/run directories under `podman unshare`.
  It rejects mismatched/shared graph arguments and symlinked directories, and
  never invokes `system reset` (which could affect machines outside the graph).
- A same-filesystem overlay bind mount survives image removal. `os.path.ismount`
  missed it; checking namespace `/proc/self/mountinfo` and explicitly unmounting
  that exact graph's overlay directory resolves EBUSY. Disposed of the failed
  Node fixture completely with the corrected helper; no shared runtime/live
  graph touched.
- Three new cleanup boundary/failure unit tests and the actual Alpine daemon
  regression pass: **4 tests, no skips**; whitespace check passes. Acceptance
  remains failed/unverified, so task 4.5 stays unchecked and progress is **18/32**.
  Pause for the operator to select bounded Podman action-copy investigation or
  the design's dedicated rootless Docker compatibility fallback. Nothing
  deployed, newly staged, committed, or archived this session.

## 1.2 Owner Authentik identity (confirmed 2026-10-08)

- Operator confirmed the owner's existing Authentik identity is the user
  **`scetrov`** (referenced in `terraform/authentik.tf` as
  `data.authentik_user.scetrov`, already member of the `All Applications`
  group).
- Recorded as non-sensitive config input `variable "forgejo_owner_username"`
  (default `"scetrov"`) in `terraform/variables.tf`. Task 2.1 will use
  `data.authentik_user[variable.forgejo_owner_username]` for the dedicated
  Forgejo access group membership.

## 5.1–5.3 Observability (discovered against real v16.0.5, 2026-10-09)

Discovery was done by running the store's real `forgejo-16.0.5` binary against a
disposable SQLite instance (no secrets, `INSTALL_LOCK = true`, `migrate` +
`admin user create` initialization) and probing the live endpoints:

- **Service-health signal:** `/api/healthz` returns `{"status":"pass","checks":
  {"cache:ping":[...],"database:ping":[...]}}` (200, no auth). It is the
  service's own health endpoint and is *not* exposed through the Caddy virtual
  host (only `/metrics` and `/api/internal*` are denied there; the site only
  proxies the normal routes, and the health check is used by Prometheus scrape
  state rather than a public path).
- **Metrics:** `settings.metrics.ENABLED = true` puts `/metrics` on the same
  `127.0.0.1:3002` listener, **bearer-token protected**: verified 401 without a
  token and 200 with `Authorization: Bearer <token>` against the real binary.
  Prometheus' `bearer_token_file` scrape option sends exactly
  `Authorization: Bearer <file contents>` (it is *not* the Basic-auth
  `authorization.credentials_file` path), which matches Forgejo's check
  verbatim. So the single `forgejo_metrics_token` secret is shared: Forgejo
  receives it through the module's `services.forgejo.secrets.metrics.TOKEN`
  credential path (which feeds `FORGEJO__METRICS__TOKEN__FILE` into
  `environment-to-ini`) and Prometheus reads the same agenix file as
  `bearer_token_file`. No auxiliary port.
- **Real metric names discovered** (job `forgejo`): `gitea_accesses` (total
  request counter), `gitea_repositories`, `gitea_users`, `gitea_issues_open`,
  `gitea_build_info{version=...}`, plus Go runtime/process metrics
  (`go_gc_*`, `process_*`, `go_goroutines`). ~26 `gitea_*` gauges + `zoekt_*`.
- **Secret hygiene:** the metrics token value never appears in the console log
  (which is what the journal → Loki pipeline ships) nor in the metrics body.
  Reconcile CLI output is already suppressed by design (task 3.5).
  Verified by `scripts/tests/test_forgejo_metrics.py` (real binary fixture).

### Files added/changed for observability

- `forgejo.nix`: `age.secrets.forgejo_metrics_token` (group `prometheus`,
  mode `0440`), `settings.metrics.ENABLED = true`,
  `services.forgejo.secrets.metrics.TOKEN` → the age path.
- `prometheus.nix`: `forgejo` scrape job (`127.0.0.1:3002/metrics`,
  `bearer_token_file=/run/agenix/forgejo_metrics_token`, `service=forgejo`) and
  the `forgejo` alert group with `ForgejoServiceUnavailable` (`up` != 1 for 5m,
  severity critical) — consistent with the existing headscale/garage rules.
- `alloy.nix`: journal relabel rule `forgejo\.service` → `service=forgejo`.
- `secrets` role + `secrets.nix`: generate/reuse `forgejo_metrics_token` and
  declare the `.age` public keys.
- `terraform/dashboards/forgejo-service.json` (uid `svc-forgejo`, repository
  palette), `grafana.tf` resource, and a `service-catalog.json` row.
- `forgejo-eval.nix`: new assertions for the metrics credential wiring, the
  private bearer scrape config, the protected token file, and the alert rule.

## 6.1 Targeted deployment path (implemented 2026-10-09)

The first-deploy chicken-and-egg: the `secrets` role's fail-fast assertion on
`forgejo_oidc_client_*` requires the generated OIDC outputs to exist, but they
are only produced after a `tofu apply` of the shared Authentik plan. The
`forgejo` consumer tag therefore assumes identity prerequisites were already
applied:

1. First deploy only: review the shared plan via `./scripts/tofu.sh -- plan`,
   then `./scripts/tofu.sh` (apply + refresh `src/generated-secrets.yml`).
   Shared-plan blast radius review is task 6.3.
2. Consumer path (steady state and rotation): `./scripts/play.sh --limit habiki
   --tags forgejo`. `play.sh` now refreshes/validates generated OIDC outputs in
   the pre-flight for the `forgejo` tag (fail-closed), then runs the `secrets`
   and `nixos` roles (both tagged `forgejo`). Identity reconciliation happens
   in the `forgejo.service` `preStart` before web startup — no second
   deployment, no runner registration, no first-login gate.

Fyne DNS-only path unchanged: `./scripts/play.sh --limit fyne --tags
local-dns`. Runbook: `docs/forgejo.md`.

### Scoped local checks (2026-10-09)

- `forgejo-eval.nix` passes (service-only Actions-off assertions, SSH, Caddy,
  OIDC, plus the new metrics/alert assertions).
- 21 python fixture tests pass (12 render, metrics, private proxy, reconcile)
  with the real Forgejo and Caddy binaries; retained experimental runner tests
  pass/skip as before.
- `tofu fmt -check` clean, `openspec validate --strict` valid, `git diff
  --check` clean, Ansible syntax OK for `forgejo`/`nixos`/`local-dns` tags.

Live acceptance (6.3–6.6) remains pending: shared-plan review/apply, Habiki
rollout, LAN/Teleport/Headscale access+denial, repeat/rotation/persistence,
and observability confirmation on the live host.
