---
name: frontier-indexer-cycle-maintenance
description: Safely maintain Frontier Indexer on Habiki when moving between EVE Frontier cycles. Verify release contracts/checkpoints and pinned images, inventory TimescaleDB, harden and test schema reset, deploy through targeted NixOS/Ansible automation, and verify indexing without flooding context with raw logs.
license: MIT
compatibility: This NixOS repository and Habiki deployment; Python 3.11+, OpenSpec, Nix, Ansible, pre-commit, SSH with noninteractive sudo, rootless Podman for isolated tests, and GitHub/GHCR access. No pip dependencies.
metadata:
  author: Scetrov
  version: "1.0"
---

# Frontier Indexer Cycle Maintenance

## When to use

- Upgrade Habiki's Frontier Indexer from one EVE Frontier cycle to the next.
- Plan or implement the accompanying image, compiled contracts, checkpoint and reset-generation change.
- Revalidate a partially completed cycle transition or recover forward after cutover using the current reset safeguards.
- Investigate whether a proposed cycle reset will affect unrelated state **before** authorizing it.

## When not to use

- Routine restarts, same-cycle image updates, or dashboard changes that do not require reindexing.
- General PostgreSQL/TimescaleDB upgrades, first-time host provisioning, other hosts, or mainnet deployments.
- Unrelated Grafana incidents; use the relevant observability investigation skill.
- A shared database, outside-schema dependencies, unknown cleanup targets, or an invalid marker: stop for an explicit reviewed plan; do not use this skill to justify deletion.
- Any operation lacking approval to discard the previous cycle's application state or coordinate Habiki's host-wide container restarts.

## Safety contract

1. Read repository instructions and the selected OpenSpec context. Infer the change only when unambiguous. Announce it and track tasks; do not mark untested work complete.
2. **Never infer approval from this skill, a command-line flag, or a report file.** Obtain operator authorization for irreversible schema loss and the actual deployment scope.
3. All mutations belong in NixOS/Ansible/OpenTofu. Use `scripts/tofu.sh` for any OpenTofu operation; never extract or print vault secrets yourself.
4. Preserve the database cluster, unrelated objects, credentials, network and telemetry. Only inventoried, explicitly approved cycle artifacts can be cleanup targets. Never prune containers globally or delete `timescaledb-data`.
5. Preserve readiness → authenticated preflight → schema reset → indexer. Stop the old writer through managed orchestration before switch. Reset must refuse a surviving writer.
6. Keep `podman run -i` for SQL heredocs, transactional DROP/CREATE, exclusive locking, monotonic generation validation, and fsync/atomic marker publication. Check actual schema removal, not merely exit status or marker existence.
7. Never decrement the marker, bypass it with null, or activate pre-transition NixOS reset code. Recovery is a forward repair; a future destructive reindex requires a separately reviewed higher generation.
8. Report blocked/failed steps and pause. A failed or stale report is not deployment evidence. Do not commit, open a PR, or deploy unless requested/approved.

## Efficient workflow

Resolve `SKILL_DIR` to the directory containing this file. Run helpers by absolute path; they discover this repository or accept `--repo`. Their compact JSON is suitable for context-mode. Store only their **non-secret reports** in a private temporary directory when reuse is useful. Read detailed references only as needed.

### 1. Establish the transition

Load the applicable OpenSpec proposal/design/spec/tasks. Ask for the target release, asset/world package addresses, checkpoint, and authorization if missing. Capture the old image/checkpoint and marker before modifying declarations:

```sh
python3 "$SKILL_DIR/scripts/host.py" inventory
python3 "$SKILL_DIR/scripts/release.py" --tag "$TAG" --asset "$ASSET" --world "$WORLD" --checkpoint "$CHECKPOINT"
```

Resolve every `review_required` flag, missing/invalid marker, unexpected consumer, outside-schema bookkeeping or dependency. Inventory is a point-in-time assessment, **not** a complete dependency proof. Inspect independent data and cross-schema views/constraints before considering `CASCADE` safe.

Release checks bind registry bytes to SHA256, select the Linux platform, match OCI labels to the release-tag commit, inspect compiled testnet contracts, checkpoint, environment support and enabled pipelines, and enforce the seven-day policy. Metadata consistency is **not** signature verification. If upstream layout, latest release or policy differs, pause; do not invent environment variables or bypass eligibility. See [workflow details](references/workflow.md).

### 2. Make minimal declarative changes

Update Habiki's pinned image/checkpoint/generation and the reusable module's image default. Preserve testnet, `PACKAGES=app,world`, concurrency `2`, stable schema name and existing ports/secrets unless an explicitly reviewed compatibility change requires otherwise. Do not reset for a routine same-cycle maintenance change.

Keep writer-stop orchestration and Alloy unit coverage intact. An empty cleanup allowlist requires **no** additional deletion mechanism. Review and stage only the intended files, preserving unrelated user work.

### 3. Validate locally

Run the compact checker using the planned declarations and the recorded previous-cycle image/checkpoint. Supply a verified digest for the disposable TimescaleDB test image; do not upgrade production TimescaleDB as a side effect.

```sh
python3 "$SKILL_DIR/scripts/checks.py" \
  --image "$NEW_PINNED_IMAGE" --generation "$GENERATION" --checkpoint "$CHECKPOINT" \
  --integration --old-image "$OLD_PINNED_IMAGE" --old-checkpoint "$OLD_CHECKPOINT" \
  --database-image "$TEST_DATABASE_PINNED_IMAGE"
```

The container test derives the new cycle from evaluated Habiki declarations; it has no Cycle 7 defaults. Tests use a rootless namespace, no production mounts or host ports, refuse existing reserved names, and remove only their own resources. Run serially. The fixture is not a complete host build; managed deployment still performs that build.

Check output must be `ok:true` with `integration_ran:true`. Formatting hooks can change files; review/restage and rerun. Retain the final report unchanged. See [script interfaces](references/scripts.md) and [failure lessons](references/lessons.md).

### 4. Deploy only after explicit approval

The actual wrapper is host-targeted, **not application-only**: it switches Habiki's host configuration and restarts other active Podman services. Confirm the approved maintenance window and previous-cycle data loss before execution.

The optional bounded runner validates fresh release evidence, passing integration evidence, unchanged deployment sources, and a fresh live inventory. It defaults to plan-only; execution requires both approval flags **after** obtaining real operator approval:

```sh
python3 "$SKILL_DIR/scripts/deploy.py" --release-report "$RELEASE_REPORT" --checks-report "$CHECKS_REPORT"
# Only after authorization:
python3 "$SKILL_DIR/scripts/deploy.py" --release-report "$RELEASE_REPORT" --checks-report "$CHECKS_REPORT" \
  --execute --approve-cycle-reset --approve-host-wide-restarts
```

It invokes only `./scripts/play.sh --limit habiki --tags frontier-indexer`, emits fixed phase names and a compact recap, and suppresses raw Ansible output. It performs no direct SQL/filesystem cleanup and never commits. Keep a detached run alive until completion; do not launch a duplicate deployment while it is running. Use the returned UTC `cutover_since` for verification.

### 5. Verify and close out

```sh
python3 "$SKILL_DIR/scripts/host.py" verify --generation "$GENERATION" \
  --image "$NEW_PINNED_IMAGE" --checkpoint "$CHECKPOINT" --since "$CUTOVER_SINCE"
```

Require active services, authenticated ordering, the intended image/marker/settings, successful migrations, advancing watermarks, Prometheus `up=1`, dashboard metric names and no database setup failures. Wait for startup/metrics readiness rather than interpreting a transient connection refusal as a permanent failure.

Verify that the wrapper's subsequent managed restarts skipped reset and preserved progress; review inventory again to confirm the approved cleanup boundary. Record evidence, immediately update OpenSpec tasks, run configured pre-commit checks, sync/archive the completed spec before any final commit/PR, and stage reviewed files. If the configured hook is absent, prompt the operator to run `pre-commit install`; do not bypass checks. If committing is separately requested, use signed conventional commits with required agent/model attribution; never disable signing.

## Output discipline

Report the planned/observed cycle settings, passed checks, unresolved risks, and the next step. Use compact helpers instead of repeated raw `podman inspect`, journal dumps, SQL table lists, registry manifests or Ansible debug output. Helpers never return passwords, complete environment/config objects, table rows, or raw logs. Preserve uncertainty: same-database ownership and absence of external consumers must be checked each cycle, not assumed from Cycle 7.
