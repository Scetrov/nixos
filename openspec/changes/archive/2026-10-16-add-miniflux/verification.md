# Miniflux implementation evidence

## Prerequisites (2026-10-16)

- Habiki reports NixOS `26.05.11829.a033e66ab94a`; its channel resolves to `/nix/store/1r7p8zzkq53ajhyl14rmiv1ay35bi9s2-nixos-26.05/nixos`.
- The deployed and local `nixos/modules/services/web-apps/miniflux.nix` have identical SHA-256 `698de7dab1851a0b4eccba03136e5613d6a7c44bf4189318a67378a47a59fa5c`.
- Selected listener: `127.0.0.1:8091`. Habiki's `ss -H -ltn 'sport = :8091'` returned no listeners; repository module inventory has no allocation for 8091. Recheck before activation.
- Upstream `createDatabaseLocally = false` omits PostgreSQL creation, local database setup and database ordering. The integration must supply its own setup dependencies.
- `RUN_MIGRATIONS` defaults to 1; `CREATE_ADMIN` also defaults to 1 and must explicitly be 0 for OIDC-only bootstrap. The service is `Type=notify`, uses `DynamicUser=true`, `PrivateUsers=true`, and restarts after five seconds on failure.
- `DATABASE_URL` defaults to null when local database creation is disabled; the module filters null environment values. Keep it null and supply only `DATABASE_URL_FILE`, avoiding conflicting direct/file variables. Miniflux 2.3.3 parses environment entries in order, with secret-file entries assigning their target option; do not rely on ordering when both forms are present.
- Use systemd `LoadCredential` to expose database and OIDC files to the dynamic user. The upstream AppArmor profile permits `/run/credentials/**` reads, but not arbitrary agenix paths. Secrets remain root-owned outside the service and must not be interpolated into Nix expressions.

## Release selection

- Primary GitHub releases API reports latest non-prerelease Miniflux **2.3.3**, published `2026-07-24T22:41:57Z`, comfortably older than seven days at verification time.
- Habiki's channel already packages 2.3.3 with source hash `sha256-zJ8ir6t3J65RTNi7XtTsbuG3VQId3xvEhLP6Cgn0+xg=` and vendor hash `sha256-+5vpLTpShQegLzFzAl7H86i71G+PXP66w9mIr440+oA=`. Select native `pkgs.miniflux`; no package override or floating additional channel is needed. Evaluation must verify the selected version before deployment.
- Reviewed public upstream security advisories: all six published advisories list fixed versions older than 2.3.3. Latest advisory `GHSA-m999-j542-5w3r` is low severity and fixed in 2.3.1. This is a check of published upstream advisories, not a claim of absence of vulnerabilities.
- 2.3.3 release notes include cross-user favicon disclosure, socket permissions, and entry-query bounds fixes. No seven-day exception is needed.

## Identity and first login

- Repository `terraform/variables.tf` records operator confirmation on 2026-10-08 that the existing Authentik owner identity is `scetrov`; `data.authentik_user.scetrov` already selects that username. Reuse this existing lookup in a dedicated Miniflux-only group without changing other groups.
- Miniflux 2.3.3 `internal/ui/oauth2_callback.go` creates a normal user when `OAUTH2_USER_CREATION=1`; it does not grant administrative rights. Normal feed-reader operation and personal OPML/API-token management do not require administrator bootstrap. No local-password account will be added.
- `internal/oauth2/oidc.go` passes the issuer/base endpoint to `oidc.NewProvider`; do not append the discovery suffix manually.

## Predeployment offline implementation verification

The following records the predeployment state; the operator deployment and subsequent live checks below supersede deployment-related status.

- Configuration was completed through routing, monitoring, deployment orchestration and operations documentation before any deployment or OpenTofu apply by this agent. Runtime fixtures, interactive access checks and final archive remained open.
- 37 Miniflux/generated-secret offline tests pass, including the new configuration/deployment suite. Expanded shared regression testing runs 47 tests (45 pass, two explicit opt-in tests skip); repository `tests/` contributes another 31 passing tests. Total: 76 passing tests and two skipped opt-in tests. Run with the project `.venv/bin/python` inside Bubblewrap; the system Python lacks PyYAML.
- Strict NixOS fixture evaluation covers enabled/disabled service and Grafana-disabled variants. It confirms version 2.3.3, loopback listener, five connections, migrations, no direct `DATABASE_URL`, OIDC-only bootstrap, three systemd credentials and setup ordering. HTTPS/API routing exists without Grafana; metrics are denied by Caddy; scrape/log labels and five-minute Grafana alert settings evaluate correctly. Disabled output removes services, credentials, virtual host and scrape, and explicitly deletes the alert.
- Offline SQL tests check safe psql password quoting, secret-free argv/SQL templates, bounded readiness retries, fail-closed outage behavior, restricted-role declarations, non-destructive SQL and redacted diagnostics. These are mocked contract tests, not evidence that SQL reconciliation, migrations or runtime credentials work against PostgreSQL/systemd.
- `scripts/tofu.sh -- validate -no-color` passes using installed providers without credentials/backend initialization. Formatting passes through the wrapper. Ansible syntax validation of the Habiki Miniflux tag passes. Shell syntax and Nix formatting pass. All configured pre-commit gates pass both for tracked files and explicitly selected new files, including redacted Gitleaks. The pre-commit hook is already installed.
- Expanded regression testing exposed an unchanged database-upgrade unit test relying on more than 1 GiB of real temporary disk capacity. Confirmed production/test files were unchanged and reproduced the sandbox's 1 GiB limit. The unit fixture now explicitly mocks sufficient capacity so it reaches its intended restore-failure path; production capacity checks are unchanged.
- Operator approved Vault access outside Bubblewrap. `scripts/provision_miniflux_vault.py` created the encrypted `miniflux_db_password` entry through captured pipes; its mocked idempotency/encryption tests pass. No plaintext credential was written to a tracked file or printed. OpenTofu provider resources and generated OIDC values are not yet applied/refreshed.
- Operator selected **Keep tests offline** when asked about native Nix builds and disposable database fixtures, then explicitly requested completion of the remaining configuration without waiting for those tests. Do not build/fetch the package or run fixtures without renewed approval. Task 3.4, including migration, password-rotation, restart, privilege and dynamic-user runtime checks, remains intentionally incomplete. No production database was accessed.

## Deployment and rollback review

- The targeted tag requires `--limit habiki`, rejects stale-refresh/target overrides, provisions only the Miniflux binding dependency graph, and relies on the secure wrapper's post-apply credential refresh before Ansible loads generated values. Check/list modes invoke no OpenTofu operations. Tests exercise ordering with stubs, not a real apply.
- The component-only NixOS run skips channel updates, blanket Podman restarts, Frontier writer transitions, Headscale enrollment and Garage provisioning. The NixOS switch still activates the entire host configuration and may restart other units whose definitions changed.
- Shared DNS aliases are applied to Habiki by the targeted rebuild; clients using Fyne also need the explicitly documented DNS-only rollout. No automated cross-host deployment is hidden inside the Habiki tag.
- `docs/miniflux.md` covers OPML-only loss/recovery, safe rotation, outbound-fetch trust and non-destructive rollback. Reviewed cleanup removes runtime/routing/scraping and explicitly deletes the Grafana rule on disablement. Shared DNS aliases require their documented removal and rollout. Identity resources and generated-secret mappings must be removed together through reviewed OpenTofu automation.
- The setup SQL contains no database/role/schema deletion, and no stop/rollback hook deletes data. Database and role remain by default; package rollback does not undo migrations. No production cleanup was executed.
- Still required after deployment approval: real SQL/migration/runtime validation, reviewed OpenTofu preview/apply, HTTPS/DNS checks against both DNS servers, OIDC allowed/denied flows, native API checks, feed/OPML operation, runtime credential consistency, metric denial/scraping, Loki ingestion and receiver delivery. Archive only after completion, before any final commit/PR.

## Post-deployment verification (2026-10-16, approximately 11:50 UTC)

The operator reported deployment. The agent performed read-only checks only: no rebuild, restart, fixture, data modification or infrastructure apply. Task 5.4 remains open because repeatability, feed operation and receiver delivery are not yet verified, and DNS rollout is incomplete.

- `miniflux`, `miniflux-dbsetup`, Caddy, Prometheus, Alloy, Grafana and the PostgreSQL container report active/success. Miniflux reports zero restarts; setup has completed successfully.
- The listener is exclusively `127.0.0.1:8091`. Private `/healthcheck` returns 200, `/v1/me` without credentials returns 401, and private `/metrics` returns 200 with 50 metric families. Prometheus reports `up{job="miniflux",service="miniflux"}=1`.
- HTTPS was checked against Habiki with an in-process DNS override while preserving the real hostname, SNI and normal certificate validation. Root and health return 200; `/metrics` and `/metrics/test` return 404; unauthenticated `/v1/me` returns 401. No TLS-verification bypass was used.
- Habiki DNS (`10.229.53.2`) returns `10.229.10.2`. Fyne DNS (`10.229.53.1`) returns no A address, and Fyne's `/etc/hosts` lacks the feed alias despite Blocky being active. The operator workstation cannot resolve the hostname normally. Pending corrective rollout: `./scripts/play.sh --limit fyne --tags local-dns`; it was not run by the agent.
- Read-only PostgreSQL catalog inspection confirms database ownership by `miniflux`; the role has no superuser, create-database, create-role, replication or bypass-RLS privileges. No application rows were read. This does not establish full cross-database isolation or rotation/restart behavior.
- Authoritative generated OIDC values match the live Authentik provider and the running service's actual systemd credentials. Its runtime database password matches Vault. Comparisons took place in memory and printed booleans only; no values or hashes were printed or persisted.
- Loki returns three Miniflux-labeled streams and seven entries for the preceding two hours. Journal metadata contains 13 service/setup records and no priority-error records; message bodies were not printed. The Grafana rule `miniflux-unavailable` is present, healthy and inactive. Actual receiver delivery remains untested. An unrelated expired Grafana Cloud context caused the all-context gcx check to fail; the explicitly selected on-premises context is online and worked for these queries.
- Still pending: Fyne DNS rollout, repeat deployment evidence, authorized/unauthorized browser OIDC checks, disabled-local-login check, authenticated API requests, feed/OPML use, notification delivery, and the declined isolated runtime tests. No task checkbox was advanced solely on the operator's deployment report.

## Operator acceptance and archive decision (2026-10-16)

After receiving the post-deployment findings, the operator stated "Confirmed working" and requested commit/push. The operator then explicitly approved archiving with documented deferrals and syncing the capability to the main specs. This is operational acceptance, not a claim that every individual test in tasks 3.4, 5.4 and 5.5 was performed. Those tasks remain unchecked for their outstanding scope. No additional independent DNS recheck or negative-authentication test was performed at this sign-off. Archive is proceeding under that explicit exception before the requested signed commit/push.

## Sources

- https://api.github.com/repos/miniflux/v2/releases?per_page=5
- https://api.github.com/repos/miniflux/v2/security-advisories
- https://github.com/miniflux/v2/releases/tag/2.3.3
- https://miniflux.app/docs/configuration.html
- https://raw.githubusercontent.com/miniflux/v2/2.3.3/internal/config/parser.go
- https://raw.githubusercontent.com/miniflux/v2/2.3.3/internal/ui/oauth2_callback.go
- https://raw.githubusercontent.com/miniflux/v2/2.3.3/internal/oauth2/oidc.go

## Approved local isolation exception

The operator approved adapting the external Bubblewrap launcher for NixOS. `/nix/store` and `/run/current-system/sw` are exposed read-only; PATH includes Git's resolved immutable store directory. No home/profile directory, credentials, sockets or host networking were added. Isolated `git status --short` succeeded with exit 0. The project remains the only persistent writable mount; the store's contents are visible to sandboxed processes. Launcher change is outside this repository at `/home/scetrov/.agents/skills/bubblewrap-isolation/scripts/run-isolated.sh`.
