# GitHub → private Forgejo mirrors

## Current state: approved public mirrors on Habiki

The module defaults to disabled/report-only. Habiki explicitly enables approved
public-only imports: `reportOnly = false`, `importApproved = true`,
`lfsVerified = true`, `privateAuthVerified = false`, with no GitHub credential.
All 35 selected repositories are private native mirrors and repeated discovery
reports 35 healthy, 192 excluded and zero errors. Actions, ingress and identity
reconciliation are unchanged. Live acceptance verified autonomous native updates,
all 2,699 branch/tag refs against GitHub, and an explicitly approved stale-status/
recovery test. The normal three-hour threshold is restored and current errors
were zero at the recorded 2026-10-22 acceptance. These are dated results, not a
fresh live inventory; use the protected report and metrics below for current state.

| Source | Case-insensitive name glob | Private destination | Forgejo ID | Planned repositories |
| --- | --- | --- | --- | --- |
| Scetrov (144595937) | `*` | `gh-Scetrov` | 6 | 14 |
| RichardSlater (630786) | `*` | `gh-RichardSlater` | 4 | 6 |
| storytold (76897702) | `*craft` | `gh-storytold` | 3 | 15 |

The operator approved namespace mapping, case-insensitive matching (including
`AniCraft`), provisioning, and subsequently the 35-repository bulk import after
capacity/LFS/observability checks. Private sources, forks and archived repositories
remain excluded. Discovery runs hourly with up to 60 seconds of jitter. Native
polling is hourly with a three-hour stale threshold; Forgejo 16.0.6 enforces a
one-minute minimum. Its default native scheduler checks due mirrors every ten
minutes, separately from the hourly discovery timer, so a due mirror may wait
until the following scheduler tick.

Live report: `/var/lib/forgejo-mirrors/report.json`, mode 0600. The historical
pre-approval inventory recorded 35 destinations, 192 exclusions, no conflicts/
errors and 2,044,647 KiB (~1.95 GiB) reported GitHub size. The source-owner and
destination mapping above preserves the approved boundary; the full dated JSON
snapshot remains in Git history, not a required operational input. Refreshed size before
import was 2,047,768 KiB with unchanged selection. This is **not** a storage bound:
LFS volume, temporary imports, overhead and growth remain unbounded. The focused
lane checks the existing 500 GiB free-space reserve before activation.

## Managed provisioning and access boundary

Run only with explicit provisioning authorization:

```bash
python3 scripts/provision_forgejo_mirrors.py --apply
```

Permanent users, private organizations and memberships are managed in
`terraform/forgejo-mirrors/main.tf`, through `scripts/tofu.sh --forgejo-mirrors`.
The PostgreSQL backend uses its own `forgejo_mirrors` schema in the existing
`terraform_state` database. Its ignored local `.terraform` cache is mode 0700
because backend metadata can be sensitive. It does not apply the shared Authentik/Grafana root.
Destroy/replacement plans are rejected and human ownership is protected.

The dedicated `forgejo-mirrors` identity is globally **non-admin**, restricted and
private, cannot create organizations or import local repositories, and has no
interactive human admission. Human access remains native Authentik OIDC.

Forgejo's native migration API requires **organization ownership**; a write team
with `can_create_org_repo` is insufficient. The operator explicitly approved
service ownership of only the three dedicated organizations. `scetrov` also
remains an owner of each. The runtime token has only
`write:repository,read:organization`, not organization-write or global admin scope.
The controller verifies the exact organization set.

There is deliberately no persistent administrative provisioning credential.
Supported native CLI commands create a unique temporary admin bootstrap identity
and a token scoped to `write:admin,write:organization,read:user`. OpenTofu uses
that credential, then automation verifies permanent human/service ownership,
removes bootstrap membership and deletes the bootstrap account (including its
token). Password and reverse-proxy authentication remain disabled. Cleanup and a
fresh-bootstrap repeat no-op plan are tested in disposable containers.

If partial provisioning leaves the bootstrap as the last organization owner,
cleanup stops for managed recovery rather than deleting data. Inspect native
account state and repair ownership through the reviewed provisioning workflow;
never purge an organization to clear an error. Existing untracked identities,
organizations or service tokens are not silently adopted.

The provider is pinned to `svalabs/forgejo` 1.6.1 and the linux/amd64 archive SHA256
in `scripts/forgejo_provider.py`. The filesystem-only mirror verifies the archive
before OpenTofu installation. At selection, 1.7.0 was still inside the repository's
seven-day update deferral; 1.6.1 was the newest eligible release. Other platforms
fail closed until their hashes are explicitly reviewed.

## Vault and runtime credentials

The source of truth is encrypted `src/secrets.yml`. Use Ansible Vault with
`~/.ansible/nixos_vault_password` (mode 0600); never paste credentials into chat,
argv, generated Nix or logs. Provisioning atomically appends only its managed
password/token keys, preserves other vault content, refuses silent replacement
and detects concurrent vault changes. Temporary plaintext plans/identities use
protected RAM-backed directories and are removed afterward.

The focused play renders only `forgejo_mirrors_token.age` for approved operators
and Habiki, copies it mode 0600 to `/root/secrets`, and agenix exposes a root-only
0400 runtime file. systemd `LoadCredential` hands the token to the dedicated
unprivileged Linux service. State is 0700, reports 0600, public metrics 0640 in an
Alloy-readable setgid directory.

Public GitHub enumeration needs **no GitHub credential**. A future private opt-in
requires explicit policy approval, a dedicated read-only Contents/Metadata token
with selected repository/organization access, `githubCredential = true` and
`privateAuthVerified = true`. Public user enumeration cannot establish private
coverage; private user discovery uses authenticated `/user/repos` with stable
owner filtering, while organization discovery uses `/orgs/{owner}/repos`.

Updating the runtime token does not revoke its predecessor. Token revocation and
rotation require a separately reviewed supported managed path; do not enable
password authentication just to use the token-management API. Disabling the
service identity via reviewed OpenTofu configuration is an account-wide access
revocation decision, not a substitute for tested per-token rotation.

## Focused deployment

```bash
# Copy only relevant files/credential; build and review dry activation.
# The explicit phase flag is required while managed policy enables imports.
./scripts/play.sh --limit habiki --tags forgejo-mirrors -- \
  -e forgejo_mirrors_imports_approved=true

# After reviewing that plan, activate and run discovery immediately.
./scripts/play.sh --limit habiki --tags forgejo-mirrors -- \
  -e forgejo_mirrors_imports_approved=true -e forgejo_mirrors_apply=true
```

This lane rejects wider host/tag overrides, performs no channel update, shared
OpenTofu refresh, recursive configuration sync, Frontier writer stop or blanket
container restart. It evaluates configuration before activation and refuses to
proceed unless the managed import phase is explicitly approved, namespace IDs
match the reviewed mapping and private/fork/archived inclusion remains disabled.
Report-only policy can still be deployed without the phase flag. Optional
`-e forgejo_mirrors_verify_acceptance=true` with apply explicitly restarts Forgejo,
runs discovery, then queues native sync only for state-owned private mirrors after
checking repository and organization IDs. Do not use it for routine deployments.

The first activation reloaded Alloy/D-Bus and refreshed tmpfiles for the new Linux
identity. Forgejo and Frontier Indexer invocation IDs were unchanged. A repeated
report run again found 35 plans, zero errors and no ownership state or imported
repositories. The hourly timer is active.

**Import rollout:** the first run recorded 32 creations and three request timeouts.
The configured systemd retry recovered all 35 as healthy without re-POSTing or
duplicating repositories. Later rebuild/restart acceptance preserved every
repository ID. Mimir recorded errors=3 followed by errors=0. Broader eligibility
still requires separate approval. Preserve ownership state after any timeout:
a failed HTTP request does not prove the remote import failed.

## Convergence, lifecycle and recovery

Forgejo performs one-way Git synchronization. Discovery creates native pull mirrors
using `service=git`, `private=true` and requested LFS support; it never pushes Git
or migrates Issues, PRs, discussions, Actions, secrets or platform metadata.

Stable GitHub repository/owner IDs map to stable Forgejo organization/repository
IDs. The reconciler writes an atomic, fsynced random ownership intent before its
only remote mutation. POST is never blindly retried. A response-lost import is
recovered only when its exact marker, canonical source URL, private mirror flag
and organization ID match. Healthy mirrors are not recreated. A lock prevents
overlapping runs; GET retries/backoff, quota deferral and startup time are bounded.

- Namespace/destination collision or identity/access errors: review ownership and
  repair through automation; never adopt or overwrite an unrelated destination.
- `pending_import_review`: check native tasks and destination first. Clear only a
  proven uncommitted intent through separately reviewed managed repair. Never
  erase the whole ownership file or re-POST an uncertain import.
- Rename, transfer, disappearance, visibility/eligibility or mapping changes:
  retain destination and state, report review status, never delete or silently
  retarget. Missing sources are also queried by stable repository ID.
- Stale/unknown native status: inspect Forgejo logs and source authorization.
  After repair, a reviewed automation request to
  `POST /api/v1/repos/{owner}/{repo}/mirror-sync` queues native re-sync; verify
  actual branch/tag/LFS content and subsequent timestamps, not just HTTP success.

## LFS, submodules and observability

The disposable 16.0.6 fixture verifies public/private native imports, automatic
Git/tag updates and initial/later LFS byte-for-byte transfers with password API
authentication disabled. Both migration and native LFS polling require the LFS
server setting. A recent Git `mirror_updated` does **not** prove LFS completeness:
native LFS failures are logged separately and must be treated as blocking
incompleteness, including warnings saying `Ignoring missing upstream LFS object`.
The native fixture reproduces that warning and verifies byte-for-byte recovery
when the upstream object is restored. Production LFS is now enabled through the
NixOS module, with persistent storage; imports remain gated separately.

Submodule URLs are not rewritten. The fixture checks unchanged `.gitmodules`
references; external/private submodule access still requires separate management.
Mirrors are not a complete disaster-recovery solution.

Journal summaries flow to Loki under `service=forgejo`,
`unit=forgejo-mirrors.service`; HTTP bodies, exception details and credentials are
suppressed. Detailed inventory stays in protected local state. Alloy's
textfile-only collector explicitly relabels `job` and `service` to
`forgejo-mirrors` and forwards through existing remote write to Mimir/Grafana.
Both paths were verified through the existing Grafana datasources; no listener,
firewall port or dashboard was added.

```promql
forgejo_mirrors_errors{job="forgejo-mirrors"} > 0
forgejo_mirrors_repository_error{job="forgejo-mirrors"} > 0
forgejo_mirrors_sync_age_seconds{job="forgejo-mirrors"}
time() - forgejo_mirrors_last_run_timestamp_seconds{job="forgejo-mirrors"} > 10800
(time() - forgejo_mirrors_last_success_timestamp_seconds{job="forgejo-mirrors"} > 10800)
  and on(instance) (forgejo_mirrors_report_only{job="forgejo-mirrors"} == 0)
```

Loki: `{service="forgejo",unit="forgejo-mirrors.service"}` for discovery and
`{service="forgejo"} |~ "failed to synchronize LFS objects|Ignoring missing upstream LFS object"`
for native LFS errors **and missing-object warnings**. Either result blocks
acceptance, regardless of a recent Git timestamp; restore source objects or
credentials and verify destination LFS bytes before declaring recovery.
Last success advances only for a fully successful apply, not report-only. Monitor
missing/stale last-run signals too: a process killed before publication cannot
report its own failure. At the recorded 2026-10-22 acceptance, an explicitly
approved one-second threshold test
emitted 35 stale errors in Mimir and stale logs in Loki; restoring 10,800 seconds
returned all 35 mirrors to healthy with zero errors. No Forgejo or Frontier
restart occurred. Do not repeat fault-injection checks without review.

## Disable and rollback

Set `mirrors.enable = false` and deploy a reviewed targeted configuration. Keep
Forgejo repositories, application identities, vault credentials and
`/var/lib/forgejo-mirrors` intact. Restore the same ownership state on re-enable;
do not downgrade Forgejo's migrated database.

Native polling is independent and **continues if discovery is disabled**. Suspend
polling only through separately approved supported API automation (verify interval
semantics first), or a managed Forgejo stop affecting the whole forge. Revoking an
upstream token merely causes private polling failures. No automatic conversion,
repository deletion or OpenTofu destroy is part of rollback.

## Local validation

```bash
python3 -m unittest discover -s scripts/tests -p 'test_forgejo*.py'
nix-instantiate --eval --strict --json --expr \
  'import ./src/roles/nixos/tests/forgejo-mirrors-eval.nix {}'
FORGEJO_MIRROR_TEST_IMAGE=codeberg.org/forgejo/forgejo@sha256:563d3222411ac993f5481b95ada90f164b04032ac43f51ebfd7fe51e8732b552 \
  FORGEJO_MIRROR_PROVISION_TEST=1 \
  python3 -m unittest scripts.tests.test_forgejo_mirror_native -v
```

The provisioning fixture uses only disposable local state through the wrapper's
fixture mode, never the vault or production backend. Native/API fixtures do not
establish live imported-source acceptance, capacity bounds, host restart recovery
or complete disaster recovery. Issue #26's evidence map distinguishes native/API
fixtures from actual production acceptance; neither timestamps alone nor initial
import success substitutes for content and failure/recovery verification.
