# Handoff: mirror-selected-github-repositories

_Updated: 2026-10-22 · Task progress: 10/10 · State: archived; issue #26 closed as completed_

## Current position

Habiki now has 35 healthy private native pull mirrors, 192 exclusions and zero
reconciliation errors. The operator approved the unchanged inventory, hourly
discovery/native polling, three-hour staleness and existing 500 GiB reserve,
conditional on capacity/LFS/observability checks, then explicitly authorized
managed LFS enablement and a reviewed Forgejo restart.

Task 3.3 is now complete. The 20:00 scheduled discovery passed; autonomous native
polling at 20:11:24–20:11:50 BST propagated later commits and all 2,699 branch/tag
refs matched. The operator explicitly approved a temporary one-second stale
threshold test: 35 Mimir errors and Loki stale logs were observed; restoring
10,800 seconds recovered 35 healthy/zero errors. Forgejo and Frontier invocation
IDs stayed unchanged. All final gates passed, the capability spec was synced and
the change archived. Issue #26 is verified CLOSED/COMPLETED with final evidence:
https://github.com/Scetrov/nixos/issues/26#issuecomment-6349434000

No commit or push. Initial durable redacted evidence map (historical):
https://github.com/Scetrov/nixos/issues/26#issuecomment-6347740632

See [acceptance.md](acceptance.md) for every issue criterion and its limitations;
[investigation.md](investigation.md) retains earlier provisioning evidence.

## Live state and evidence

- Selection: Scetrov=14, RichardSlater=6, storytold=15; case-insensitive `*craft`
  includes `AniCraft`. Public/non-fork/non-archived only; no GitHub credential.
- Private namespace IDs: gh-Scetrov=6, gh-RichardSlater=4, gh-storytold=3. Stable
  GitHub owner IDs remain 144595937/630786/76897702.
- Permanent account `forgejo-mirrors` is globally non-admin/restricted, owner of
  exactly those organizations with `scetrov` retained as human owner. Token scopes:
  `write:repository,read:organization`. No temporary bootstrap remains.
- Runtime `reportOnly=false`, `importApproved=true`, `lfsVerified=true`,
  `privateAuthVerified=false`, `staleAfterSeconds=10800`; no private/fork/archived
  inclusion. Persistent ownership contains 35 sources and destination IDs.
- First import run: 32 creations and three transport timeouts (artcraft,
  photocraft, pdfcraft). The configured systemd retry recovered 35 healthy/zero
  errors without duplicate imports. Do not re-POST uncertain imports or delete
  ownership state. Mimir observed errors=3 then 0 and report_only=0.
- After an explicit acceptance rebuild/restart, all 35 private mirror IDs still
  matched ownership state. Anonymous repository API access returned 403.
- Initial source comparison checked 2,698 branch/tag refs: 34/35 repositories
  matched; photocraft/main advanced from 46394c59765122c32c190e4493100c9a517f1c90
  to 6649b78526826cc543f5aced1195c06c0b7e850a. Managed native sync advanced the
  destination to the new SHA. This was manually queued, NOT observed hourly
  production polling. Native automatic branch/tag polling passed in containers.
- Runtime LFS is enabled with persistent storage via upstream NixOS LFS module.
  Production originally had LFS disabled; the regression test went red then green.
  Native fixture verifies initial/later LFS bytes and missing-object recovery.
- **Important:** Forgejo logs missing upstream LFS as the warning `Ignoring missing
  upstream LFS object`, not necessarily `failed to synchronize LFS objects`.
  Both are blocking; the runbook query now matches both. No matching production
  logs in checked intervals. A recent Git timestamp does not prove LFS completeness.
- Pre-import GitHub size 2,047,768 KiB, unchanged selected destinations; free space
  2,808,183,140,352 bytes. Post-import free 2,805,132,951,552 bytes. LFS/workspace/
  overhead/growth remain unbounded; the play checks a 500 GiB reserve, not a quota.
- On-prem gcx context `metrics-net-scetrov-live` is healthy. Mimir datasource
  `mimir` has 35 sync-age series and recent last-success; Loki datasource `loki`
  has native/controller logs. Do not change unrelated expired Cloud contexts.
- Forgejo restarted for LFS and acceptance; latest invocation ID:
  `4a204c2d649c40a99915667bcdb78796`. Frontier remains unchanged at
  `1b0060ee6c744bce9c3a2503f30d30f1`. No channel update or blanket restart.

## Managed deployment

The mirror module now enables `services.forgejo.lfs.enable` when mirrors are
enabled; `lfsVerified` remains a separate attestation. The focused deployment
requires explicit phase approval when policy enables imports, fixes all three
namespace IDs/owner policies and refuses broader eligibility.

```bash
# Build and review dry activation (no switch).
./scripts/play.sh --limit habiki --tags forgejo-mirrors -- \
  -e forgejo_mirrors_imports_approved=true
# After reviewing the plan, switch and run discovery.
./scripts/play.sh --limit habiki --tags forgejo-mirrors -- \
  -e forgejo_mirrors_imports_approved=true -e forgejo_mirrors_apply=true
```

Optional `-e forgejo_mirrors_verify_acceptance=true` with apply explicitly restarts
Forgejo, runs discovery, and queues native sync after checking every managed
repository/organization ID and private mirror flags. Do not use for routine runs
or mistake queued sync for autonomous hourly acceptance. No source mutations.

## Security and working tree

- Branch main. Unrelated Hermes archive and automatic-SSO artifacts were staged
  before this work; preserve them. Never reset or commit the complete index blindly.
- Intended edits/evidence are staged separately. Generated `*.age` remain ignored;
  do not force-add. Tracked encrypted vault is the source of permanent credentials.
- Never print vault values. Password file `~/.ansible/nixos_vault_password` is 0600.
  Runtime token root 0400; state/report 0700/0600; Alloy metrics 0640.
- All OpenTofu operations use `scripts/tofu.sh`; `--forgejo-mirrors` selects its
  isolated root/backend schema. No production provisioning was repeated this session.
- Existing provider pin/hash/provenance limitations remain in investigation.md.
  No dependencies added or updated this session.

## Validation

- 46 Forgejo tests with digest-pinned native/provisioning fixture enabled:
  7 existing opt-in skips, no failures. Includes new native LFS warning/recovery.
- Both Forgejo Nix evaluations pass against 16.0.6. Focused Ansible syntax and
  strict selected-change OpenSpec validation pass.
- Installed pre-commit hook verified. All configured `pre-commit run --all-files`
  gates pass, including redacted gitleaks, nixfmt and wrapper-based tofu fmt.
- Repeat native fixture:
  `FORGEJO_MIRROR_TEST_IMAGE=codeberg.org/forgejo/forgejo@sha256:563d3222411ac993f5481b95ada90f164b04032ac43f51ebfd7fe51e8732b552 FORGEJO_MIRROR_PROVISION_TEST=1 python3 -m unittest scripts.tests.test_forgejo_mirror_native -v`.

## Finalization

Live autonomous propagation and explicitly approved stale/recovery verification
are complete. The current threshold is explicitly 10,800 seconds, the controller
report is 35 healthy/192 excluded/zero errors, and Mimir errors=0. The normal
scheduler checks due mirrors every ten minutes; the discovery timer is separate.
Recent autonomous commits include vectorcraft/main
`4b7969a05c6b24b9878c7cc59bcf0da0ae63d790` (20:07:07 BST).

Completed: 46 tests (7 existing opt-in skips), both Nix evaluations, strict
OpenSpec validation and all configured pre-commit gates. Archive-generated extra
EOF whitespace was fixed by the configured hook and the full gate passed again.
Main spec: `openspec/specs/forgejo-github-mirroring/spec.md`. Archive:
`openspec/changes/archive/2026-10-22-mirror-selected-github-repositories/`.
Final evidence is published and #26 verified CLOSED/COMPLETED. Intended files
are staged, unrelated staged work preserved. No commit or push was attempted.
Any future commit must be separately authorized, signed and attributed.

Do not repeat controlled threshold tests without review; historical stale errors
are expected and do not indicate a current unresolved incident.
