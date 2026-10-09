# Workflow and boundaries

## Repository touchpoints

| Purpose | Path |
| --- | --- |
| Habiki declaration | `src/roles/nixos/files/device-configuration/habiki.nix` |
| Reusable module and startup chain | `src/roles/nixos/files/etc/nixos/modules/frontier-indexer.nix` |
| Reset implementation | `src/roles/nixos/files/etc/nixos/modules/frontier-indexer-reset.sh` |
| Managed stop/switch/start | `src/roles/nixos/tasks/rebuild.yml` |
| Existing host-wide restart loop | `src/roles/nixos/tasks/podman.yml` |
| Targeted deployment wrapper | `scripts/play.sh` |
| Log coverage | `src/roles/nixos/files/etc/nixos/modules/alloy.nix` |
| Dashboard metric compatibility | `terraform/dashboards/frontier-indexer.json` |
| Nix evaluation fixture | `tests/frontier-indexer-eval.nix` |
| Cycle-neutral real-image integration | `tests/frontier_indexer_container_check.py` |
| Forward recovery runbook | `docs/frontier-indexer-cycle-recovery.md` |

## Before implementation

Use the current OpenSpec status/apply instructions, not guessed filenames. A missing prerequisite or ambiguous cycle is a blocker. Record expected release contracts/checkpoint and a snapshot of the active image/checkpoint/marker, active consumers, schemas and cleanup targets. Revalidate Linux architecture and release eligibility every time. Do not invent target-cycle values from historical references.

The registry helper verifies index, child-manifest and image-config bytes against content hashes. It follows annotated tags to commits and compares source/revision/version labels. This proves consistency of downloaded metadata, not that an untrusted publisher built the image correctly. Inspect published signatures/attestations and upstream build provenance when available; do not claim verification without evidence.

The default helper enforces latest stable release and seven days of release age. A CVSS >= 7.0 exception requires an explicit documented policy decision and revised verification evidence; the helper intentionally has no eligibility-bypass flag.

## Database safety

`DROP SCHEMA indexer CASCADE` can remove dependent objects in other schemas. Independent unrelated tables can survive while dependent views/foreign-key constraints disappear. The helper checks common relation/function/constraint/rewrite dependencies and highlights non-infrastructure schemas; it is **not an exhaustive dependency walk**. Investigate unexpected types, extension-owned objects, shared schemas or indirect dependencies separately before deletion.

TimescaleDB catalogs, internal chunks, TOAST storage and extension infrastructure are not independent application archives. Let PostgreSQL/TimescaleDB manage their lifecycle when resetting hypertables. Never remove cluster files manually.

Runtime inventory excludes contents of the cluster, password and environment files. It reads only allowlisted non-secret environment settings and the numeric marker. An unknown file/path is a review flag, not authorization to delete it. Sampled application client addresses are compared with the current indexer's container addresses; a quiet external consumer may escape that snapshot.

## Cutover and recovery

1. Agree the irreversible reset and **host-wide** maintenance window.
2. Stage reviewed declarations and pass actual old-writer/image migration/reset tests.
3. Stop the old writer via Ansible before switch. The reset guard must independently refuse a surviving container.
4. Authenticate before any reset; a password mismatch is repaired through existing managed preflight, without exposing secrets.
5. Execute DROP/CREATE transactionally with SQL stdin forwarded. Serialize through marker publication.
6. Verify schema removal and fresh migrations, then durable generation and advancing checkpoints.
7. Confirm an equal-generation rebuild/restart preserves state. Record the journal's reset-applied/skipped events without dumping raw logs into context.

On failure, pause and retain current safety logic. Do not activate old NixOS generations, lower the marker, disable it, or claim discarded data can be recovered by configuration rollback. Equal-generation redeployment can repair the current cycle without another reset. Missing/invalid markers require explicit review outside the automatic deployment runner. Database and filesystem marker recovery must be coordinated; they are not transactional together.

## Portability and standard

`https://agenticskills.io/` is a directory describing the portable SKILL.md format. The formal specification is `https://agentskills.io/specification`.

This skill uses the required name/description YAML frontmatter, standard optional license/compatibility/string metadata, a matching lowercase-hyphen directory, executable helpers under `scripts/`, and progressively loaded `references/`. It grants no tool permissions. Its workflow intentionally depends on this repository and Habiki; copying it to a different infrastructure requires explicit adaptation and review, not silently changing its scope.
