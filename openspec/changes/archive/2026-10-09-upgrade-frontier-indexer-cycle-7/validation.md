# Implementation validation evidence

## Release verification — 2026-10-09 UTC

Task 1.1 verified against upstream GitHub metadata and the GHCR registry:

- Latest published release: `v0.4.0`, published `2026-09-29T18:43:13Z`; older than the repository's seven-day deferral window.
- Release metadata: https://api.github.com/repos/Algo-Net/Frontier-Indexer/releases/tags/v0.4.0
- Registry manifest bytes for `ghcr.io/algo-net/frontier-indexer:v0.4.0` hash to `sha256:20c64a1c96fa96c29569fa8343398566d22cb17fb62b1dd8ee6a0d21d7af5fc9`, matching the design.
- Linux amd64 image manifest: `sha256:184271dbb2fa12d3fa6dc34970cc58a0a6714cd252817982161f54d192d06385`.
- Habiki declares `nixos_architecture: x86` in `src/inventory.yml`, compatible with the image platform. Live architecture confirmation was unavailable.
- Image OCI source label: `https://github.com/Algo-Net/Frontier-Indexer`.
- Image OCI version label: `v0.4.0`.
- Image OCI revision label: `7b94c78f646d88dc8cd0f24689cd9c059d7c2bea`, matching the commit referenced by upstream's annotated `v0.4.0` tag.
- This establishes metadata consistency, not independent signature or build-attestation verification.

## Source compatibility — task 1.2

Reviewed `src/lib.rs`, `src/main.rs`, `src/config.rs`, `.env.sample`, and `pipelines.toml` at release commit `7b94c78f646d88dc8cd0f24689cd9c059d7c2bea`.

- `TESTNET_WORLD_PACKAGES` contains both supplied Cycle 7 addresses, labeled Assets v1 and World v1.
- `.env.sample` declares `FIRST_CHECKPOINT=387251154` and `DB_SCHEMA=indexer`.
- Configuration supports `PACKAGES=app,world`, testnet, checkpoint and ingestion concurrency settings.
- Without `PIPELINES`, main loads `pipelines.toml`; all listed pipelines are enabled.
- The database URL sets `search_path` to `DB_SCHEMA`; main creates the schema and applies embedded migrations.
- Running the actual pinned image remains a separate validation task (4.2).

## Live read-only inventory — task 1.3

The initial SSH attempt exceeded a 20-second deadline. A user-authorized retry succeeded with a longer deadline; Habiki reports `x86_64`. No remote mutation or deployment was performed.

- The Frontier cluster has one non-template database: `postgres`.
- `indexer` has 60 table/view relations, including `__diesel_schema_migrations` and `watermarks`; all 41 hypertables belong to `indexer`.
- `public` has no table/view relations. Other observed schemas are PostgreSQL/TimescaleDB/Toolkit infrastructure. No continuous aggregates were reported.
- The only sampled application connection originates from `10.89.2.26`, matching the running `frontier-indexer` container. Other sessions are database background workers. This is a point-in-time observation, not a guarantee that external clients never connect.
- The indexer container has no runtime mounts. `/var/lib/frontier-indexer` contains only `timescaledb-data`, `schema-reset-generation`, `db-password`, and `indexer.env`. No separate cycle caches/dumps/exports were found in that deployment state directory.
- Current reset marker is `6`.
- Sampled relation dependencies outside `indexer` were PostgreSQL TOAST storage; TimescaleDB internal storage is managed by the extension and must not be removed by filesystem cleanup.
- Explicit extra cleanup allowlist: empty. Do not add filesystem deletion or container pruning; schema reset is the only authorized cleanup target.

## Implementation and predeployment checks

- Cycle 7 image/checkpoint/generation declared in Habiki and the reusable module default.
- Minimal NixOS evaluation using Habiki's actual Frontier settings produces readiness → preflight → reset → indexer, with no dependency cycle. Generated scripts build successfully.
- Eleven reset unit regressions passed, using the actual reset shell script and a fake container CLI.
- Alloy's existing selector covers all unchanged unit names.
- Isolated rootless integration passed authenticated generated preflight, refusal with an actual running Cycle 6 image, and password-mismatch repair.
- **Integration failed after reset:** `indexer.watermarks` still existed even though generation `7` was published. The inherited reset invocation uses `podman run` without `-i`; the SQL heredoc is not delivered to the container.
- A separate isolated stdin probe reproduced the issue: without `-i`, the container read no input and exited `1`; with `-i`, it read `stdin-probe` and exited `0`.
- Task 3.4 was reopened, then fixed with `podman run -i`. The strengthened regression fake reproduced six failures before the fix and all eleven tests passed afterward.
- Real rootless integration passed after the fix: old bookkeeping removed, unrelated rows preserved, concurrent resets serialized, failed authentication leaves the marker unchanged, and the actual Cycle 7 image migrates successfully.
- All 59 pipeline watermarks initialized from the declared checkpoint and advanced to `387251218` in the final predeployment run.
- Rebuilt the Nix-generated reset wrapper, performed an equal-generation restart, and verified a sentinel table inside `indexer` survived. Stale/invalid generations were refused without losing indexed state.
- An early post-restart metrics check raced process readiness; the test now waits for endpoint availability. Final integration passed and all existing dashboard `frontier_indexer_*` metric names supplied by the image were present. Chain-head metrics remain supplied by the unchanged external exporter.
- Targeted Ansible syntax check passed. Scoped configured pre-commit hooks passed, including gitleaks, Nix formatting and YAML validation; the pre-commit hook is installed.
- Habiki Frontier settings and the generated dependency graph were evaluated using a minimal NixOS fixture with a mocked age-secret declaration. This is not a complete host toplevel build; the targeted managed deployment must still perform that build.
- All test containers/networks were cleaned up. No production reset or deployment has occurred.

Container test images were used by digest: TimescaleDB `sha256:56b0bf42cec250b0fbf4b3ca155f60553a5dfadc90c578a0421f84b331dda920`; Cycle 6 indexer `sha256:31c4e04def1f2bad8b0ca8d0aef4d1d5f23e791a442a1c02687446384d7c24f9`. Production TimescaleDB configuration is unchanged. ## Managed deployment and live verification — 2026-10-09 UTC

- `./scripts/play.sh --limit habiki --tags frontier-indexer` completed with exit `0`. The full host configuration built and switched successfully. The existing NixOS role also restarted Habiki's other active Podman services; this workflow is host-targeted, not application-only.
- Ansible stopped the old indexer before switch. The live reset journal confirms actual `DROP SCHEMA`, `CREATE SCHEMA`, `COMMIT`, and one successful application of generation `7`.
- The running image is the verified Algo-Net digest. Its runtime settings are testnet, `PACKAGES=app,world`, concurrency `2`, and checkpoint `387251154`; compiled contracts match the release source verified above.
- Final sampled preflight exit timestamp `87108358220` precedes reset start `87108363365`; reset exit `87108569765` precedes indexer start `87109320000` (systemd monotonic microseconds). All three units report successful results; indexer and TimescaleDB are active.
- The live marker is `7`; the new schema has 64 applied migrations and 59 pipeline watermarks. Watermarks advanced from `387251510–387251511` in the first live sample to `387253579–387253585` after the managed restart loop.
- Prometheus reports `up{job="frontier-indexer"}=1`; the live endpoint exports 80 metric names. Dashboard metric compatibility passed against the same pinned image in isolated testing.
- No database connection/setup/schema/migration failure messages were found in the post-cutover journal window.
- Subsequent managed restarts logged `schema reset skipped: no new generation` twice, while retaining marker `7` and advancing watermarks. The old application schema/bookkeeping was removed; no separate Cycle 6 runtime artifact existed to clean up and no runtime archive was created.
- Remaining design questions are resolved: no additional cleanup targets, no sampled external database consumer requiring coordination, and managed writer exclusion verified by the stop-before-switch workflow plus the running-container reset guard.
- No new ports, routes, DNS aliases or identity integrations were introduced. Existing Alloy selectors and Prometheus/Grafana integrations remain in place.

## Finalization

Final staged-file pre-commit checks and all eleven reset regressions passed after deployment. The user selected main-spec synchronization and archive; OpenSpec updated three requirements and added two, then archived the change as `2026-10-09-upgrade-frontier-indexer-cycle-7`. All reviewed required files are staged. No commit or PR was requested or created; any future commit must be signed and include the required agent/model attribution.
