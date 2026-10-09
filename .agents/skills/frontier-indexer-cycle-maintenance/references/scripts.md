# Compact helper interfaces

Run with Python 3.11+; no additional Python packages are installed. Set `SKILL_DIR` to this skill's absolute directory. Every public helper supports `--help`. Reports are JSON; `release`, `host`, and `checks` emit one compact object. `deploy` emits bounded JSON lines for fixed phases plus a final report.

## release.py — external read-only verification

```sh
python3 "$SKILL_DIR/scripts/release.py" --tag "$TAG" --asset "$ASSET" --world "$WORLD" \
  --checkpoint "$CHECKPOINT" --architecture amd64
```

Exit `0` means every check passed; exit `1` includes failing check names or a bounded error. Uses anonymous GitHub/GHCR HTTPS requests with timeouts. Registry bearer tokens stay in memory and are never printed or written. The report includes the exact image reference, commit, release age, observation timestamp and pipeline count, not raw source/manifests.

An upstream configuration/layout change fails closed for manual inspection. All compiled testnet packages, environment arguments and enabled pipelines must remain compatible with the requested transition.

## host.py — live read-only inventory and verification

```sh
python3 "$SKILL_DIR/scripts/host.py" inventory --ssh-target scetrov@10.229.10.2
python3 "$SKILL_DIR/scripts/host.py" verify --generation "$GENERATION" --image "$NEW_PINNED_IMAGE" \
  --checkpoint "$CHECKPOINT" --since 2026-10-09T10:00:00Z
```

`--repo` overrides repository discovery; `--timeout` defaults to 180 seconds. SSH uses BatchMode, connection/keepalive limits and existing host-key validation. The remote Python payload executes only read-only Podman inspection, systemd/journal inspection, filesystem reads, SELECT queries and localhost metrics requests. Root access is via noninteractive sudo; no vault extraction or interactive password prompt occurs.

Inventory reports schemas/counts, common outside-schema dependencies, bookkeeping locations, consumer addresses, known-safe settings, generation validity and bounded artifact paths. `ok:true` means collection succeeded, **not** that `review_required:true` is safe to ignore. It deliberately does not list application rows, full environment values, image configuration or journal text. First provisioning/absent containers is outside this skill's supported automatic workflow.

Verification requires explicit expected values and an ISO-8601 timestamp with a timezone. It summarizes service ordering, marker/image/settings, watermarks, migration count, metric compatibility, Prometheus health and database setup error count. A false result means pause or wait for known startup readiness, then rerun; no repair is attempted. No checkpoint-rate claim is made from a single sample: compare consecutive reports to confirm continued advancement.

## checks.py — repeatable local checks

Stage only reviewed intended files first. Then:

```sh
python3 "$SKILL_DIR/scripts/checks.py" --image "$NEW_PINNED_IMAGE" \
  --generation "$GENERATION" --checkpoint "$CHECKPOINT" \
  --integration --old-image "$OLD_PINNED_IMAGE" --old-checkpoint "$OLD_CHECKPOINT" \
  --database-image "$TEST_DATABASE_PINNED_IMAGE"
```

Without `--integration`, no containers are launched, but the result **cannot** authorize deployment. The helper checks declared settings/dependencies, reset and skill regressions, generated scripts, targeted Ansible syntax, configured staged-file pre-commit hooks, and whitespace. Stops at the first failed step. No secrets or full check output enter context.

With integration, the test starts genuine pinned old/new images against disposable rootless TimescaleDB. It tests writer exclusion, authentication repair/failure, SQL forwarding/removal, concurrent resets, migrations/progress, an equal-generation rebuilt-wrapper restart, stale/invalid guards, unrelated row preservation and dashboard metrics readiness. The synthetic old test marker is the new generation's immediate predecessor; the actual live marker is separately inventoried/validated. All supplied test images must be fully qualified and digest-pinned. No silent mutable-tag fallback occurs.

Reports bind to a SHA256 fingerprint of the relevant host sources/tasks, test and skill code, inventory/playbook, wrapper and pre-commit configuration. Hook/source changes invalidate evidence and require restaging/rerunning. This is a drift check, not an authorization/signature mechanism or a full NixOS toplevel build. Vault contents are not read/fingerprinted; runtime secret handling remains in repository automation.

## deploy.py — approved wrapper, bounded output

Save successful release/check reports in a private temporary directory outside Git, then validate the plan:

```sh
python3 "$SKILL_DIR/scripts/deploy.py" --release-report "$RELEASE_REPORT" --checks-report "$CHECKS_REPORT"
```

Execution is opt-in:

```sh
python3 "$SKILL_DIR/scripts/deploy.py" --release-report "$RELEASE_REPORT" --checks-report "$CHECKS_REPORT" \
  --execute --approve-cycle-reset --approve-host-wide-restarts
```

Flags record an already obtained operator decision; they are not permission to make that decision on the operator's behalf. The runner requires matching release evidence no older than 24 hours, every required check including integration, unchanged source fingerprint, and fresh inventory on Habiki without unresolved review flags. It refuses missing/invalid/stale markers. Equal generation is permitted for forward recovery, never to repeat destructive reset.

Only `scripts/play.sh --limit habiki --tags frontier-indexer` mutates the host. The runner has no direct SQL/delete/restart paths. It streams fixed phases and integer recap counters, discards raw logs rather than persisting potentially sensitive debug payloads, and records a UTC cutover timestamp. It does not impose an arbitrary timeout on the deployment process; let it finish or handle interruption deliberately. Do not detach it with a mechanism that kills the child on timeout.

## Evidence capture without context flooding

Use a private temporary report directory (`umask 077`) and shell redirection for compact **non-secret JSON** if the next helper needs a file. Process larger subprocess output inside `ctx_execute`, not in conversation memory. The helpers already reduce raw input to answers; do not wrap them in a loop that repeatedly prints full output or launch concurrent container/deployment runs.

Never save raw journals, complete `podman inspect`, environment files, vault output or credential-bearing connections as project evidence. On a failure, the JSON check/phase identifies where to triage; inspect only bounded relevant diagnostics with the appropriate tools/skills. Do not blindly retry a destructive phase or activate an old generation.
