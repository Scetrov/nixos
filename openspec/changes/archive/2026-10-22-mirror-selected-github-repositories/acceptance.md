# Issue #26 acceptance evidence

Final evidence summary; issue verified CLOSED/COMPLETED:
https://github.com/Scetrov/nixos/issues/26#issuecomment-6349434000

Initial redacted progress summary (historical; recorded remaining gates):
https://github.com/Scetrov/nixos/issues/26#issuecomment-6347740632

## Current outcome

Habiki has 35 healthy private native pull mirrors: Scetrov=14,
RichardSlater=6, storytold=15. The approved mapping is `gh-Scetrov` (ID 6),
`gh-RichardSlater` (ID 4), `gh-storytold` (ID 3). Matching is case-insensitive,
including `AniCraft`; private, forked and archived sources remain excluded.
The operator explicitly approved the unchanged 35-repository selection, hourly
cadence, three-hour stale threshold and existing 500 GiB reserve, conditional on
capacity/LFS/observability checks. No GitHub credential is used.

**Live acceptance passed on 2026-10-22.** The 20:00:11 BST scheduled discovery
completed at 20:00:17 with 35 healthy, 192 excluded and zero errors. Without a
manual sync, native polling advanced all 35 mirror timestamps at
20:11:24–20:11:50 BST. At 20:12:28 all 2,699 branch/tag refs matched upstream,
including later commits such as vectorcraft/main
`4b7969a05c6b24b9878c7cc59bcf0da0ae63d790` (20:07:07 BST). This confirms actual
autonomous content propagation, not merely timestamp freshness.

The operator then explicitly approved a controlled stale-status test. Targeted
automation temporarily changed the freshness threshold to one second; Mimir
observed 35 errors and Loki contained `mirror_stale` events. The expected service
failure is a test outcome, not an unresolved incident. Restoration in a finally
block returned the threshold to 10,800 seconds; the deployment passed, the report
returned 35 healthy/192 excluded/zero errors and Mimir returned errors=0. Forgejo
and Frontier invocation IDs were unchanged. No source mutation or native polling
suspension was used. The change is archived at
`openspec/changes/archive/2026-10-22-mirror-selected-github-repositories/` and its
four-requirement capability is synced to
`openspec/specs/forgejo-github-mirroring/spec.md`. No commit or push is claimed.

## Acceptance matrix

| Issue criterion | Evidence and limitation |
| --- | --- |
| All eligible Scetrov sources mirrored | Live discovery: 14 private mirrors, IDs match ownership state; public/non-fork/non-archived policy. |
| All eligible RichardSlater sources mirrored | Live discovery: 6 private mirrors, IDs match ownership state. |
| Only matching storytold sources mirrored | Live discovery: 15 private mirrors; case-insensitive `*craft`; complete selection unchanged from approved report. |
| New matching repositories imported automatically | API fixture covers subsequent discovery/import and repeat convergence; hourly production timer enabled. No new upstream repository was created for live acceptance. |
| Subsequent branches/tags sync without manual intervention | Pinned native fixture verifies automatic branch/tag polling. Production initial comparison matched 34/35 repositories across 2,698 branch/tag refs; photocraft/main advanced upstream from `46394c59765122c32c190e4493100c9a517f1c90` to `6649b78526826cc543f5aced1195c06c0b7e850a`. Managed native sync advanced the destination to the latter SHA. This was explicitly queued, **not** proof of an hourly production poll. Later autonomous production polling at 20:11:24–20:11:50 BST propagated new source commits and all 2,699 refs matched at 20:12:28, without another manual sync. Forgejo's default scheduler checks hourly-due mirrors every ten minutes. |
| Repeated reconciliation is idempotent | Initial run: 32 creations, three transport timeouts. Configured retry: 35 healthy, zero errors, one restart; all three uncertain imports recovered without duplicates. Later rebuild/restart discovery again preserved all 35 IDs. |
| Namespaces preserved or mapped | Explicit approved `gh-` mappings and stable organization IDs above; independent ownership state. |
| Nonmatching/unrelated repositories untouched | 192 excluded in repeated live discovery; controller rejects unowned destinations. Collision/nonmatching fixtures pass; no destination adoption/deletion is performed. |
| Lifecycle changes non-destructive | API fixtures cover rename/transfer/delete/visibility and review statuses; operational runbook documents preservation and manual review. No destructive source mutation was attempted live. |
| Private sources retain access controls if enabled | Private-source inclusion is disabled. All 35 public-source destinations are private; anonymous API request returns 403. Native fixture tests private upstream auth and outsider denial. |
| Credentials least-privilege/runtime-only | Globally non-admin service, ownership of exactly three dedicated organizations, repository-write/organization-read token. Protected agenix/systemd runtime credential; no GitHub token. Prior provisioning/native fixtures verify scope and token hygiene; no persistent bootstrap admin. |
| Failures/staleness visible and recoverable | Live Mimir observed errors=3 then 0; 35 sync-age series, report_only=0 and advancing last-success. Loki has controller/native logs. Native fixture reproduces `Ignoring missing upstream LFS object` and byte-for-byte recovery. Both that warning and `failed to synchronize LFS objects` are blocking acceptance. API fixtures exercise stale classification. Explicitly approved production threshold test (one second) produced 35 Mimir errors and Loki stale events; restoring 10,800 seconds recovered 35 healthy and Mimir errors=0 without restarting Forgejo/Frontier. |
| Rebuild/restart persistence | Repeated focused rebuild/switch and explicitly requested Forgejo restart preserved all 35 private mirror IDs and ownership. Frontier invocation remained `1b0060ee6c744bce9c3a2503f30d30f1`. |
| Documented/tested | `docs/forgejo-mirrors.md`, API/native/provisioning/deployment fixtures and Nix evaluations. Final gate results are recorded in HANDOFF.md. Mirrors exclude GitHub platform metadata and preserve submodule URLs. |

## LFS and capacity

Production initially had LFS disabled. A regression assertion failed on that
setting, then passed after enabling `services.forgejo.lfs.enable` within the
mirror module. The upstream NixOS module provisions persistent storage and the
LFS JWT secret. Targeted dry activation showed only Forgejo, its secret-generation
unit and tmpfiles affected; runtime LFS and storage were verified after switch.

The digest-pinned Forgejo 16.0.6 native fixture verifies initial/later public and
private LFS bytes, unchanged submodule references, native missing-object warning
and recovery. The original error-only Loki filter missed the warning case and
has been expanded. The production query returned no matching failures in the
checked interval; this is not a proof that every historical LFS pointer is complete.
The live metadata database contained zero LFS objects at the initial check.

Pre-import reported GitHub size: 2,047,768 KiB; free space:
2,808,183,140,352 bytes. After import: 2,805,132,951,552 bytes free. GitHub size is
not a bound for LFS, workspace, overhead or growth. The focused lane enforces a
500 GiB free-space pre-activation reserve, not an ongoing storage quota.

## Final validation

All 46 Forgejo tests passed with the digest-pinned native/provisioning fixture
enabled (7 existing opt-in skips). Both Forgejo Nix evaluations passed against
16.0.6. Strict OpenSpec validation and every configured pre-commit gate passed,
including redacted gitleaks, nixfmt and wrapper-based tofu fmt. The main spec was
synced and the change archived; intended files are staged separately from
pre-existing unrelated Hermes/SSO work. No signing, commit or push was attempted.

## Recheck without mutating sources

Use the explicit `metrics-net-scetrov-live` gcx context. Mimir datasource: `mimir`;
Loki datasource: `loki`.

```promql
forgejo_mirrors_errors{job="forgejo-mirrors",host="habiki"}
max_over_time(forgejo_mirrors_errors{job="forgejo-mirrors",host="habiki"}[1h])
forgejo_mirrors_sync_age_seconds{job="forgejo-mirrors",host="habiki"}
time() - forgejo_mirrors_last_success_timestamp_seconds{job="forgejo-mirrors",host="habiki"}
```

```logql
{service="forgejo",unit="forgejo-mirrors.service"}
{service="forgejo"} |~ "failed to synchronize LFS objects|Ignoring missing upstream LFS object"
```

For future checks, observe native polling after a real upstream change without
queuing manual sync. Verify actual changed branch/tag content, stable IDs and
private access, not timestamps alone. The controlled stale test above was
explicitly approved; do not repeat threshold changes or suspend polling without
operator review. Recovered service failures remain visible historically in Loki
and Mimir, as expected; use current error values to distinguish recovery.
