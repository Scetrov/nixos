## 1. Confirm release and cleanup boundaries

- [x] 1.1 Revalidate v0.4.0 release eligibility, registry digest, Habiki architecture and image provenance against the release source.
- [x] 1.2 Confirm both supplied Cycle 7 contract addresses, checkpoint `387251154`, environment compatibility and all-pipeline behavior in the pinned release.
- [x] 1.3 Inventory Habiki's application schemas, migrations/watermarks, cycle-specific caches/dumps/exports and active database consumers read-only; record explicit cleanup targets or evidence no extra cleanup is needed.

## 2. Declare the Cycle 7 deployment

- [x] 2.1 Update Habiki to the Algo-Net v0.4.0 digest-pinned image, checkpoint `387251154` and reset generation `7`, retaining testnet and concurrency `2`.
- [x] 2.2 Align the reusable module image default with the verified digest-pinned release; preserve secrets, network, ports and existing package selection.

## 3. Harden reset and transition automation

- [x] 3.1 Reorder service dependencies to readiness → authenticated preflight → schema reset → indexer without dependency cycles.
- [x] 3.2 Implement and verify writer exclusion during transition from an already-running indexer using managed systemd/Ansible coordination.
- [x] 3.3 Validate reset generations and markers; permit missing/older markers, skip equal generations and fail closed for stale generations or invalid markers.
- [x] 3.4 Serialize reset execution and atomically publish the marker only after successful schema reset; prevent startup on reset or marker-publication failure.
- [x] 3.5 Automate removal of any confirmed obsolete artifacts using validated explicit targets; preserve cluster, unrelated state, secrets and reset marker, and avoid global pruning.
- [x] 3.6 Document forward recovery preserving generation `7`, including the prohibition on blindly activating old NixOS generations; preserve Alloy coverage for any changed units.

## 4. Validate before deployment

- [x] 4.1 Validate Nix syntax/evaluation, generated runtime settings and systemd dependency graph for Habiki.
- [x] 4.2 Test the pinned image against isolated disposable TimescaleDB containers for migrations, contract configuration and checkpoint initialization.
- [x] 4.3 Test a running old-writer transition, first reset, equal-generation restart and rebuild, credential mismatch repair, and concurrent starts; verify no writer runs during reset.
- [x] 4.4 Test stale and invalid markers, failed authentication, reset failure and marker-publication failure; verify fail-closed behavior and successful retry without unintended data loss.
- [x] 4.5 Verify cleanup affects only inventoried targets and preserves unrelated schemas/files; verify the no-extra-artifacts path performs no broad deletion.
- [x] 4.6 Run repository checks and configured pre-commit checks; if the hook is absent, prompt for `pre-commit install` rather than bypassing validation.

## 5. Deploy and verify Cycle 7

- [x] 5.1 Coordinate any required consumer downtime and deploy using `./scripts/play.sh --limit habiki --tags frontier-indexer` only after predeployment checks pass.
- [x] 5.2 Verify TimescaleDB health, preflight-before-reset ordering, generation `7`, clean application state, successful migrations and active indexer service.
- [x] 5.3 Verify checkpoint progress from `387251154`, supplied contract configuration, absence of database setup failures, Prometheus scrape health and existing Grafana dashboard compatibility.
- [x] 5.4 Confirm Cycle 6 runtime artifacts are removed without retaining a Cycle 6 archive, and verify a subsequent managed restart does not reset Cycle 7 state.

## 6. Finalize the change

- [x] 6.1 Record validation and deployment evidence, resolve remaining open questions, and review changed files for secrets or unintended infrastructure changes.
- [x] 6.2 Archive the completed OpenSpec change before the final commit/PR, then stage all reviewed required files.
- [x] 6.3 If committing or opening a PR is requested, use a signed conventional commit with model and Pi Coding Agent attribution; stop if signing fails. (Not requested; no commit or PR created.)
