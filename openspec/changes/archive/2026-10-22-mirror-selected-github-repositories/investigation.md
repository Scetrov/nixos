# Implementation and rollout evidence

## Latest state: approved imports active

The operator's subsequent "Proceed" authorized managed LFS enablement and the
reviewed Forgejo restart. The mirror module now enables upstream NixOS LFS
storage/configuration. Both Nix evaluations pass; the missing-LFS regression
assertion was observed failing before the fix and passing afterward.

Native failure injection revealed that missing upstream LFS objects produce
`Ignoring missing upstream LFS object`, which the former error-only query missed.
The fixture and documented blocking query now cover that warning and verify
byte-for-byte recovery after restoring the upstream fixture object. Production
native/controller log transport and the expanded query were checked through Loki.

Approved import deployment created 32 mirrors and recorded three transport
failures. The existing bounded systemd retry recovered all 35 private mirrors,
without duplicate imports. Mimir recorded errors=3 then 0. A subsequent focused
rebuild, explicit Forgejo restart and no-op discovery preserved all 35 IDs.
Frontier's invocation ID remained unchanged. A real photocraft/main advance
propagated through a managed manually queued native sync; this is not autonomous
production polling evidence.

See [acceptance.md](acceptance.md) for the complete criterion map and limitations,
and [the durable issue summary](https://github.com/Scetrov/nixos/issues/26#issuecomment-6347740632).
Subsequent live acceptance passed: the 20:00:11 BST scheduled discovery completed
successfully at 20:00:17; all 35 native mirror timestamps advanced autonomously at
20:11:24–20:11:50. At 20:12:28 all 2,699 branch/tag refs matched GitHub, including
later source commits (vectorcraft/main `4b7969a05c6b24b9878c7cc59bcf0da0ae63d790`,
20:07:07 BST). Forgejo's default scheduler checks due mirrors every ten minutes;
this is separate from the discovery timer.

The operator explicitly approved a controlled production stale-status test.
Targeted automation temporarily set a one-second threshold, exposing 35 Mimir
errors and Loki `mirror_stale` logs. A finally-block restoration returned the
threshold to 10,800 seconds, report to 35 healthy/192 excluded/zero errors and
Mimir errors=0. Neither Forgejo nor Frontier restarted. No source mutations or
polling suspension occurred. All 10 tasks are complete; final tests, strict
validation and pre-commit gates passed. The change is archived and the main spec
synced. Issue #26 is verified CLOSED/COMPLETED with
[final evidence](https://github.com/Scetrov/nixos/issues/26#issuecomment-6349434000).
No commit or push. Earlier sections below are historical checkpoints, not the
current import authorization/state.

## Conditional import approval and safety-gate blocker

On resumption the operator approved proceeding with the recorded 35 public,
non-fork, non-archived repositories, hourly discovery/native polling, three-hour
staleness and existing 500 GiB reserve, conditional on successful refreshed
inventory/capacity and production LFS/error-observability checks. Material
inventory changes or failed checks require stopping.

Read-only production checks found 35 planned, 192 excluded, zero errors,
2,047,768 KiB reported source size and 2,808,183,140,352 bytes free. Ownership
state remains absent; report-only/import gates remain true/false respectively.
Forgejo and Frontier invocation IDs remain unchanged from the evidence below.

**Failed preflight:** evaluated NixOS configuration has
`services.forgejo.lfs.enable = false` and
`services.forgejo.settings.server.LFS_START_SERVER = false` (absent setting
resolved to false). Native LFS completeness cannot be asserted. No deployment,
configuration change or import was attempted. Pause for guidance on managed LFS
enablement and its Forgejo restart; blocking error-observability verification
and all live imported-source acceptance remain outstanding.

This conditional approval supersedes prior statements that no import approval
exists, but it does not satisfy the failed safety gate or complete task 1.2.

## Status and authorization (prior report-only stage)

Six of ten tasks are complete. The operator approved namespace mapping,
case-insensitive matching, automated identity/organization provisioning, vault
access through `ansible-vault`/`~/.ansible/nixos_vault_password`, and focused
Habiki report-only deployment. They separately approved a temporary provisioning
admin identity and permanent ownership of the three mirror organizations by the
globally non-admin service account. **Imports remain unapproved and disabled.**
Issue #26 stays open; no archive, commit, push or closure is claimed.

## Installed contracts and least privilege

- Habiki runs Forgejo 16.0.6; installed Swagger was inspected over SSH. Anonymous
  version API access is denied, as expected for the private service.
- Native migration supports `service=git`, separate runtime auth fields,
  `repo_owner`, `mirror`, `mirror_interval`, `private` and `lfs`. Status exposes
  `mirror_updated`; the mirror-sync endpoint queues work rather than proving it.
- A dedicated write team, even with `can_create_org_repo`, was rejected by the
  real API: "Given user is not owner of organization." The operator approved the
  required three-organization ownership; no global-admin permission is granted
  to the service identity. Its token has `write:repository,read:organization`.
- GitHub public discovery needs no token and correctly distinguishes users from
  organizations with complete pagination. Private/fork/archived inclusion remains
  opt-in and is not authorized in this rollout.
- Native LFS import and later polling depend on the LFS server setting. Native
  LFS errors are logged separately: Git mirror timestamps alone do not establish
  LFS completeness. Production LFS/error-path validation remains an import gate.
- The installed minimum mirror interval is one minute. Proposed eventual native
  polling is hourly with a three-hour stale threshold.

## Production provisioning evidence

Permanent state is managed by `terraform/forgejo-mirrors/main.tf` through the
mandatory wrapper, with isolated `pg` schema `forgejo_mirrors` in the existing
`terraform_state` database. The shared Authentik/Grafana root was not applied.

| Private organization | Stable Forgejo ID | Permanent owners |
| --- | --- | --- |
| gh-Scetrov | 6 | scetrov, forgejo-mirrors |
| gh-RichardSlater | 4 | scetrov, forgejo-mirrors |
| gh-storytold | 3 | scetrov, forgejo-mirrors |

Native account listing after provisioning contains only `scetrov` and
`forgejo-mirrors`: **zero temporary bootstrap accounts remain**. The service is
restricted, globally non-admin and belongs to exactly these three organizations.
Password/proxy authentication stayed disabled. Human admission remains Authentik.

The password and scoped runtime token were added to encrypted `src/secrets.yml`,
preserving other plaintext entries. Runtime token delivery uses
`forgejo_mirrors_token.age` with operator/Habiki recipients, root-only agenix
0400 output and systemd credentials. The vault password file was found at 0644
under a 0755 directory and restricted to 0600; no password value was printed.

## Dependency provenance and bounded review

Provider 1.6.1 was released 2026-09-18. Latest release 1.7.0 was published
2026-10-15 17:40 UTC and was still inside the seven-day deferral when selected;
its release notes did not announce a CVSS >= 7 remediation. The selected
linux/amd64 archive is pinned to SHA256
`2a9bec6b5780b5b583a0b921c189d5b89761d6bd86b8df2497437756c4c84903`,
checked before installation through a filesystem-only provider mirror. The
OpenTofu filesystem installation reports no registry signature authentication;
the explicit reviewed upstream archive hash provides integrity pinning.

Bounded read-only source review covered the tagged entrypoint, provider
configuration and user/organization/team/membership resource paths (six files,
~73.5 KiB), tag tree `75b502b47169d3a0429e294bbfc5c4ba40ab811c`.
Observed credential flow was environment/configuration → Forgejo SDK → configured
API host, with masked token logging. No shell execution mechanism was found in
those reviewed paths. SDK dependencies, binary/source correspondence and complete
build provenance were not independently audited; this is not a safety certification.

## Live report-only inventory

Authoritative recorded snapshot: [report-only-inventory.json](report-only-inventory.json).
The protected live report is `/var/lib/forgejo-mirrors/report.json`.

| Source | Stable GitHub owner ID | Type | Selected | Excluded |
| --- | --- | --- | --- | --- |
| Scetrov | 144595937 | User | 14 | 19 |
| RichardSlater | 630786 | User | 6 | 120 |
| storytold | 76897702 | Organization | 15 | 53 |

Total: **35 planned**, **192 excluded**, **zero conflicts/errors**. `AniCraft`
correctly matches the approved case-insensitive suffix. Source eligibility and
exclusions are recorded without a GitHub credential.

GitHub reported size: **2,044,647 KiB (~1.95 GiB)**, up slightly from the initial
2,037,157 KiB discovery checkpoint as sources changed. This does not bound LFS,
import workspace, overhead or growth. Host free space at preflight was
2,808,234,643,456 bytes (~2.55 TiB), before the existing 500 GiB storage reserve.
LFS measurement and explicit final capacity/import approval remain pending.

After two report-only runs all three destination repository lists were empty,
`ownership.json` did not exist, `reportOnly=true`, and `errors=0`. No source or
unrelated repository was modified.

## Targeted activation and observability

Before deployment, 51 existing Nix files matched local configuration; Forgejo and
Alloy matched repository HEAD with only intended local changes pending. The
rendered ACME file was preserved. The focused `forgejo-mirrors` lane copied only
its modules, host policy and encrypted credential, without channel updates,
recursive sync, shared OpenTofu refresh or blanket container restarts.

Dry activation showed Alloy/D-Bus reload and tmpfiles refresh for the new Linux
identity. Forgejo and Frontier Indexer invocation IDs were unchanged before/after:

- Forgejo: `e3b2a8deac1f4080b1c0e61ce8d427c2`.
- Frontier Indexer: `1b0060ee6c744bce9c3a2503f30d30f1`.

The hourly timer is active, the oneshot exits successfully, and the evaluated
configuration has report-only mode and all import/private/fork/archived gates
closed. Credential/state/report/metrics modes are 0400/0700/0600/0640 as intended;
the runtime token is absent from the service journal.

Grafana verification used the explicit on-prem `metrics-net-scetrov-live` context:

- Mimir returns `forgejo_mirrors_report_only{job="forgejo-mirrors",host="habiki"}=1`
  and `forgejo_mirrors_errors{job="forgejo-mirrors",host="habiki"}=0`.
- Loki returns mirror summaries with `service=forgejo`,
  `unit=forgejo-mirrors.service`.
- Verification caught the embedded exporter's default `integrations/unix` job
  label; an explicit target relabel fixed it, and the documented job-filtered
  queries now return the live series. The correction reloaded Alloy only.
- An unrelated expired Grafana Cloud default context was not changed; the
  explicitly selected on-prem context was healthy.

## Local validation and reproduced fixture issues

API fixtures verify matching, multiple pages, collisions, lifecycle safety,
atomic restart recovery, locks, rate limits/backoff and redaction. Native fixtures
verify initial/later Git/tag and LFS bytes, unchanged submodule URLs, private
access denial, scoped non-admin access and restart persistence. Provisioning
fixtures additionally verify early-failure cleanup, permanent ownership, temporary
account deletion and a no-op repeat plan under a fresh bootstrap, with password
API authentication disabled.

Reproduced fixture constraints were fixed, not guessed: correct rootless CLI
config path; one-minute interval floor; actual bytes (not nested LFS pointers)
when the contents API applies `.gitattributes`; a permanent human administrator
for last-admin cleanup protection; valid team naming; name-based organization
lookup for a fresh nonmember admin provider identity; and the native ownership
requirement. The deployment used NixOS's actual Bash path after a missing
`/bin/bash` failed safely and cleaned its temporary identity.

Both Nix evaluations, strict OpenSpec validation and configured pre-commit gates
are part of the recorded validation workflow. Final rerun results are summarized
in `HANDOFF.md`; no fixture proves live imported-mirror acceptance.

## Remaining acceptance gates

- Explicit approval of final inventory/capacity/cadence and production imports.
- Production LFS configuration and blocking error monitoring verification.
- Approved initial imports, a live no-op reconciliation and later native updates.
- Live restart/rebuild persistence and stale/failure recovery evidence.
- Archive only after acceptance, then any authorized signed commit/PR and durable
  evidence publication. Keep issue #26 open until every criterion is supported.

## Primary sources

- Installed Swagger: `http://127.0.0.1:3002/swagger.v1.json` via SSH.
- https://github.com/Scetrov/nixos/issues/26
- https://codeberg.org/forgejo/forgejo/src/tag/v16.0.6/routers/api/v1/repo/migrate.go
- https://codeberg.org/forgejo/forgejo/src/tag/v16.0.6/services/mirror/mirror_pull.go
- https://codeberg.org/forgejo/forgejo/src/tag/v16.0.6/routers/api/v1/api.go
- https://docs.github.com/en/rest/repos/repos#list-repositories-for-a-user
- https://github.com/svalabs/terraform-provider-forgejo/releases/tag/v1.6.1
- https://github.com/svalabs/terraform-provider-forgejo/releases/tag/v1.7.0
- https://github.com/svalabs/terraform-provider-forgejo/releases/download/v1.6.1/terraform-provider-forgejo_1.6.1_SHA256SUMS
