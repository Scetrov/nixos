# Historical paused handoff — 2026-10-14

> Superseded after resumption: Authentik 2026.8.3 is active, OIDC smoke tests are operator-confirmed, the destructive admin blueprint writer is fixed, provider plan/apply are no-op, and final Habiki deployment/health checks pass. See `tasks.md`, `design.md` and `pr-body.md` for final evidence. The original pause notes below are retained only as maintenance history; do not treat their resume command or pending-work list as current instructions.

## User instruction

Pause after finishing the current Codex socket fix so the user can clear context. **That task is complete and deployed. Do not continue until asked.** Keep this a practical homelab maintenance job, not an enterprise rollout; downtime is acceptable. No background rollout is left running.

## Live state at pause

- Habiki: `scetrov@10.229.10.2`, passwordless sudo works. Inventory also contains `bullit` (local) and `fyne`; there is no inventory host named `home`.
- All three databases (OnCall, Dependency-Track, Authentik) have been dumped, cold-copied, restored into isolated PG17 containers, database lists compared, and installed. Live server version: **17.11**.
- OnCall Redis is **8.10.2**. The formerly anonymous `/data` volume is now the persistent named volume `oncall-redis-data`, seeded from the saved RDB.
- Authentik is intentionally STILL on the old **2026.5 image**, now anchored to its running digest: `ghcr.io/goauthentik/server@sha256:5a77d345a63452cda3762c573070e50a9e4be7f500fb1d82de18d95f705a898c`. Repository default is already 2026.8.3, but that activation is pending.
- Database-only stage is active through `/etc/nixos/database-upgrade-stage.nix`, which imports normal configuration and forces the old Authentik image. Keep this file until the next activation stage completes.
- Latest Ansible run: **failed=0**, all application health checks passed. `systemctl --failed` reports **none**.
- Codex 0.162.0 and `ai-usage-exporter` are active; exporter `/metrics` on port 9188 returns 200.
- Authentik `http://127.0.0.1:9000/-/health/ready/`, DT `http://127.0.0.1:8081/health`, and OnCall `http://127.0.0.1:18080/health/` all return 200.
- The whole-host switch also activated the other Habiki module image pins. Ansible component tags do NOT isolate NixOS module activation.

## Backups — do not delete before 2026-10-21 17:51:36 UTC

Host root-only backup directory:

`/var/lib/component-upgrade/20261014T175136`

Contains:
- `manifest.json` with original generation and source data paths, plus `prepared: true`.
- `previous-system`: GC root retaining the pre-maintenance NixOS generation.
- `dump.rdb`.
- `oncall-postgres/dump.sql` (~379 KB) and `cold-pg16/`.
- `dtrack-db/dump.sql` (~883 MB) and `cold-pg16/`.
- `authentik-postgresql/dump.sql` (~63 MB) and `cold-pg16/`. This includes **terraform_state** as well as Authentik and postgres.
- Each original data directory is also retained beside the active directory as `*.pg16-before-upgrade`.

Do NOT rerun the default `migrate` action: the data is already PG17. Do not roll back healthy databases merely because the earlier Codex start failed; that separate problem is fixed.

## Resume next time (after the user asks)

Continue the SAME prepared maintenance run, without repeating dumps or restores:

```sh
scripts/play.sh --limit habiki --tags database-upgrade -- \
  -e upgrade_confirm=true \
  -e upgrade_action=resume \
  -e upgrade_backup_dir=/var/lib/component-upgrade/20261014T175136
```

Default `upgrade_database_only=false` will finish the reviewed **Authentik 2026.8.3 activation**, check application health, and remove the temporary stage file. The last successful run explicitly set `-e upgrade_database_only=true` to pause before this step.

Then remaining tasks include:
1. Authentik migrations/health and actual Forgejo + DT OIDC smoke tests (tasks 4.1–4.2).
2. Update stale Authentik 2026.5 comments in `terraform/main.tf`; validate via the mandatory wrapper (4.3–4.4).
3. Provider changes in `terraform/main.tf` are NOT yet made: grafana 4.47.0 → 4.49.0; random ~>3.0 → design target ~>3.9. Be aware that Terraform `~>3.9` still permits later 3.x minors; inspect the intended constraint before claiming strict minor pinning.
4. All OpenTofu operations must use `scripts/tofu.sh`. The Authentik role was repaired to use that wrapper rather than invoking tofu directly. Wrapper init output goes to stderr so `output -raw` stdout stays machine-readable.
5. Post-maintenance Loki/Grafana check, sign-off, PR body including backup locations/version/deferred table, archive OpenSpec BEFORE final commit/PR, signed Conventional Commit with model + Pi Coding Agent Co-Authored-By trailers.
6. No commit or PR has been created. Most changes are staged; final documentation/staging should be rechecked. Existing pre-commit hook is installed.

Rollback if actually needed (same backup path):

```sh
scripts/play.sh --limit habiki --tags database-upgrade -- \
  -e upgrade_confirm=true -e upgrade_action=rollback \
  -e upgrade_backup_dir=/var/lib/component-upgrade/20261014T175136
```

Rollback retains failed PG17 data and restores original PG16 directories, previous generation and Redis RDB. Repository pins remain new; normal Habiki Ansible preflight refuses a rebuild over PG16 data.

## Codex task just completed

The first database-only host switch returned failure solely because Codex 0.162.0 changed Unix transport security. DBs were healthy and Authentik upgrade did not run. Reproduced locally:
- 2770 parent → security rejection.
- 2750 parent → server starts, but exported path is a symlink to a private container path, so a host readiness probe cannot connect.

Fix:
- `pkgs/codex-app-server-image.nix`: launch Codex on private `/tmp/codex-private.sock`; relay shared `/run/codex-app-server/control.sock` with `socat`; supervise both children; include coreutils for the bounded wait.
- `modules/ai-usage.nix`: runtime directory 2750, socket 0660, readiness timeout 60 seconds.
- `tests/ai-usage-eval.nix`: expected directory permissions updated.
- `scripts/tests/test_codex_socket_container.py`: explicit rootless integration test verifies a host-side WebSocket initialize/account-read handshake, real socket (not symlink), and mode 0660.
- Rebuilt and tested locally, then resumed database-only activation successfully. Live ownership: runtime `2750 codex-app-server:ai-usage-exporter`; socket `660 codex-app-server:ai-usage-exporter`.

## Other completed work

- All Section 2 image pin edits and documented exceptions are complete; 12 registry digests previously reverified against design table.
- Section 5 complete: Codex 0.162.0, coordinated module/test tag; Rust 1.99.0 with renamed `rust-1_99.nix`; pre-commit-hooks v6.0.0 anchored to commit `3e8a8703264a2f4a69428a0aa4dcb512790b2c8c`.
- Rust overlay: `f91010a5c1b6125b715eb78a84fb5dd8fb74a2b0`, `sha256-HJ4TEF3j7HmLYeEP/PtqjeiBX/6TppXB2qY53HcrWbs=`. Released Oct 1, overlay Oct 8; evaluated successfully.
- Codex nixpkgs revision `1c18abadea1a7d275e35a09495fd563c25b75753`, correct **unpacked NAR** fetchTarball hash `1rna5my9cjxna9x60vr2jlxchwrd5xmkqhmvlqwykahyx7sx5qan`. Do NOT reuse the erroneous compressed-download/RFC4648 hash from earlier conversation. Existing `codex.src.outputHash` assertion remains correct.
- Codex source/cargo hashes are in the updated image Nix file and pass assertions.
- `src/upgrade-databases.yml` + `src/roles/nixos/files/upgrade_databases.py` implement the simple explicit downtime workflow. `scripts/play.sh` dispatches the `database-upgrade` tag to that separate playbook and requires exact `--limit habiki`.
- Design D4/migration plan corrected: ordinary component-tagged runs copy all modules and switch the whole host; `oncall` has no deployment tag, while `authentik` normally doesn't rebuild NixOS.
- Default provider pins and stale comments still pending; Authentik source pin alone does NOT mean task 4.1 is complete.

## Verification and useful logs

- Real local pinned PG16→PG17 test preserves rows in two databases and a login role. Seven unit/behavior tests plus that integration test passed (8 migration tests total).
- Rootless Codex socket container test passed. Nix image build and AI usage evaluation assertions passed. Pre-commit passed.
- Script unittest discovery previously passed (35 tests before the final regression tests were added; several external/live fixtures skipped).
- Baseline Loki check worked with integer `1` hour. Fractional `0.25` is NOT supported by its GNU date expression. Baseline already had Frontier Indexer, syncthing and session-scope warnings; compare fresh logs rather than attributing the whole hour to maintenance.
- Local controller logs (not committed): `/tmp/nixos-database-upgrade.log` (initial run, Codex failure); `/tmp/nixos-codex-resume.log` (successful database-only run); `/tmp/nixos-upgrade-backup-path`; `/tmp/nixos-codex-fixed-image`; `/tmp/nixos-observability-before.log`.

OpenSpec `tasks.md` is the main task ledger. Todo #9 (Codex regression) is complete; #3 remains pending for retention/PR bookkeeping and the overall continuation. Do not archive or claim the whole upgrade complete yet.
