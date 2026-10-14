## Context

The fleet (habiki + home hosts, Ansible-managed NixOS) pins software across three surfaces:

1. **Container images** in `src/roles/nixos/files/etc/nixos/modules/*.nix` — mostly version tags, several floating (`:latest`, `:stable`, `2-alpine`), only `frontier-indexer` anchored by sha256 digest.
2. **Custom Nix packages** in `src/roles/nixos/files/etc/nixos/pkgs/` — Rust toolchain (via pinned rust-overlay) and the codex app-server image (via pinned nixpkgs revision importing `pkgs.codex`).
3. **Terraform** in `terraform/main.tf` — provider version constraints for goauthentik, caddy, grafana, random.

A review on 2026-10-14 found most components behind latest stable, Authentik split across incompatible lines (image 2026.5 vs provider 2026.8.0), and no supply-chain anchoring for most images. All target versions and digests for this design were resolved from the upstream registries on 2026-10-14 and are listed in `tasks.md` for auditability.

**5-day cooldown rule:** a release is only eligible if published ≥ 5 days before the change date. As of 2026-10-14, codex `0.162.1` (2026-10-09) and grafana provider `4.50.0` (2026-10-14) are inside the window and are deliberately **not** the targets.

## Goals / Non-Goals

**Goals:**
- Bring every managed component to the latest stable release that has passed the 5-day cooldown.
- Anchor every public-registry image by tag **and** sha256 digest (multi-arch index digest), generalising the frontier-indexer pattern.
- Reconcile the Authentik image and Terraform provider onto one major line (2026.8.x).
- Upgrade Postgres 16→17 and Redis 7→8 for OnCall/Authentik/Dependency-Track with backup/rollback.
- Keep the change deployable via `./scripts/play.sh --limit <host> --tags <component>` (targeted runs per host).

**Non-Goals:**
- Dependency-Track 5.x major migration (4.14.5 is the in-line target; 5.2.0 tracked as follow-up).
- Postgres 18 (one major ahead of 17; 17 is the current LTS-ish baseline — 16→17 is the safe step).
- Home-assistant `2026.10.1` (2026-10-10, inside cooldown; `2026.10.0` is the eligible target).
- Replacing the NixOS channel, OpenTofu, or `google-antigravity-cli` (unpinned/unverifiable upstreams — out of scope).

## Decisions

### D1 — Target versions (frozen at proposal time)

| Component | From | To | Digest (multi-arch index, captured 2026-10-14) |
|-----------|------|----|------------------------------------------------|
| home-assistant | `:stable` | `2026.10.0` | `sha256:1b64d38f38d922bf9d59336451fd6453e1d614f934456af4ee3d2a51061be3a4` |
| python-matter-server | `:stable` | `8.1.2` | `sha256:6827e352011e2d8c2bde771e446fcf72acc49150ef66bad978816bac1762aad3` |
| authentik server | `2026.5` | `2026.8.3` | `sha256:ab9b4e8cc4ab3f8d1198d2db6aeea66bafea1963b3f2843589e0d163f97d9849` |
| dependencytrack apiserver/frontend | `4.14.1` | `4.14.5` | `4d41f29c…` / `d675efbd…` |
| postgres | `16-alpine` | `17-alpine` | `sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24` |
| redis | `7-alpine` | `8-alpine` | `sha256:3811787313eba226a2ef38658c6ccb91cd5e110edc89c37767de373120a0e5a0` |
| caddy (hermes) | `2-alpine` | `2.11.7-alpine` | `sha256:d8542f48d34a9cf4e4c11a478865229840e87e4c96ea3f439101f31a5d35f75f` |
| grafana/oncall | `:latest` | `v1.16.11` | `sha256:9abc7342e10022da5893867789a91112fe366b3cd064a07a32d752f9de395fe5` |
| grafana/mcp-grafana | `:latest` | `2.0.2` | `sha256:78d208116ec52b09b44f0eca66892073b39aefcb64483c54d43255c8eab7e97a` |
| timescaledb-ha | `pg17` (floating) | `pg17@sha256:20534b8a…` | digest-anchored (see D3) |
| hermes-webui | `:latest` | `latest@sha256:5fb831ca…` | digest-anchored exception (see D3) |
| codex | `0.145.0` | `0.162.0` | nixpkgs source + cargo hashes (see D5) |
| rust | `1.97.0` | `1.99.0` | rust-overlay rev (see D5) |
| pre-commit-hooks | `v5.0.0` | `v6.0.0` | git ref |
| grafana TF provider | `4.47.0` | `4.49.0` | registry |
| random TF provider | `~> 3.0` | `3.9.1` | registry (exact pin selected by operator) |

Alternatives considered: bumping everything to the absolute newest (rejected — violates the 5-day cooldown), leaving postgres at 16 (rejected — two majors behind, AGENTS.md Concurrency Rule).

### D2 — Digest anchoring format

Images are referenced as `registry/repo:tag@sha256:<64-hex>` (the OCI form NixOS `docker-containers` accepts). Digests are the **multi-arch manifest index** digest (what `Docker-Content-Digest` returns for the tag), so amd64/arm64 hosts both resolve. Full digest values live in the table above and are re-verified at implementation by pulling through the registry token flow before commit.

Rationale: tags are mutable and registry-controlled; digests are content-addressed (OWASP A03/A08). The frontier-indexer module already proves this pattern works in this codebase.

### D3 — TimescaleDB-HA and private-registry exceptions

The `timescaledb-ha` tag list is not reliably enumerable from this environment (registry API returned a corrupted name list), so the exact `pg17-tsX.Y.Z` tag could not be confirmed. Decision: keep the `pg17` tag but anchor the current image with its index digest (`sha256:20534b8a06680956336604f3735d5811807f5244c6a364c761a70dea9c63de36`). This freezes today's image (TimescaleDB 2.30.2 generation); future upgrades re-pin the digest. `nousresearch/hermes-agent` (private GHCR, unresolvable) stays `:latest` but is added to a documented exception comment; `hermes-webui` (public but version-less tags) is digest-anchored on `latest`.

Alternative: skip digests for these two (rejected — inconsistent enforcement weakens the policy).

### D4 — Postgres 16→17 and Redis 7→8 migration strategy

In-place major upgrade of a live container volume is not supported for Postgres. Implementation inspection found that component tags do **not** isolate NixOS activation: a rebuild copies all modules and switches the whole host. There is no OnCall deployment tag, and `authentik` previously only selected application configuration. Use one explicit homelab maintenance run instead; downtime is acceptable, and no availability framework is required.

1. Run `scripts/play.sh --limit habiki --tags database-upgrade -- -e upgrade_confirm=true`. This selects the separate `src/upgrade-databases.yml` playbook, not the ordinary deployment roles.
2. Build first, preserving the running Authentik image by its immutable digest for the database-only stage. Stop all three application stacks, snapshot Redis, and capture complete `pg_dumpall` dumps (including roles and the `terraform_state` database) under a root-only host backup directory.
3. Stop each PG16 server and cold-copy its data directory. Restore each dump into an isolated pinned PG17 container with no network or published ports. SQL errors fail the run; compare restored database lists. Keep every original untouched until all three restores pass.
4. Install restored directories, retaining both cold copies and the original PG16 directories. Switch NixOS once with the old Authentik image and check readiness, then switch to the reviewed 2026.8 image and check all three applications.
5. Keep backups and the old generation's GC root for ≥ 7 days. An explicit rollback invocation with the same backup directory restores the retained PG16 originals and previous generation. Failures stop the run and retain backups rather than discarding evidence or automatically retrying.

Redis 7→8: live inspection found an anonymous `/data` volume. Snapshot `dump.rdb` and copy it into a new named `oncall-redis-data` volume before the switch; the module now mounts that volume. Rollback copies the saved snapshot into the old-generation Redis container and restarts that container without replacing its anonymous volume. Ordinary Habiki NixOS deployments refuse activation while any existing managed data directory is pre-PG17.

Alternative considered: `pg_upgrade` inside a scratch container (rejected — adds an image not in the pinned set and the data volumes are container-owned, making dump/restore simpler and uniform).

### D5 — Codex 0.145.0 → 0.162.0 (nixpkgs pin bump)

The codex image is built from `pkgs.codex` in a **pinned nixpkgs revision** (`9bc02893134c…`), with assertions on version, source rev, `outputHash`, and cargo hash. Upgrading codex requires a nixpkgs revision whose `pkgs/by-name/co/codex/package.nix` builds 0.162.0. Decision: bump `nixpkgsRevision` + `nixpkgsHash` to the newest nixpkgs master commit (as of implementation day, ≥ 5 days old) that provides codex 0.162.0, and re-derive `codexSourceHash`/`codexCargoHash` from that package.nix. The existing assertion block becomes the verification mechanism — no new checks needed. Update the image tag references in `ai-usage.nix` (`codex-app-server:0.145.0` default) and `tests/ai-usage-eval.nix` in lockstep.

Runtime verification found a 0.162 transport change: the advertised Unix socket is now an absolute symlink into the container's private `/tmp/codex-daemon-10001/` directory, and group-writable rendezvous directories are rejected. Keep the existing exporter endpoint with a small in-container `socat` relay to Codex's private socket. The host runtime directory is now setgid `2750` (no group write), the exported socket remains `0660` for `ai-usage-exporter`, and readiness allows 60 seconds. The wrapper supervises both processes. This was reproduced and verified in a rootless container, then deployed successfully on Habiki; do not revert to directly exposing the container-local symlink.

Alternative: vendor the codex 0.162.0 source tarball directly (rejected — duplicates what nixpkgs already pins and hashes, and diverges from the current pattern).

### D6 — Rust 1.97.0 → 1.99.0 (rust-overlay bump)

`pkgs/rust-1_97.nix` imports rust-overlay at a pinned rev that only contains 1.97.0. Decision: bump rust-overlay to a recent pinned rev containing stable 1.99.0, bump the attrset key to `"1.99.0"`, rename the file to `rust-1_99.nix`, and update the import in `user-scetrov.nix`.

Alternative: use `pkgs.rust-bin` without the overlay (rejected — the overlay exists to get extensions pinned together; changing the mechanism is scope creep).

### D7 — Authentik line reconciliation

Bump only the image (`2026.5` → `2026.8.3`); the Terraform provider is already `2026.8.0` (latest in registry). The 2026.5→2026.8 server upgrade runs Authentik's own DB migrations on first boot against the (already-migrated) Postgres 17 data. The stale comment in `terraform/main.tf` about "2026.5.2 / pbm_uuid" is rewritten to state the alignment rationale.

Alternative: downgrade the provider to match the image (rejected — provider 2026.8.0 is the registry latest and matches the target image line).

### D7a — Preserve application memberships during admin reconciliation

OIDC verification exposed a competing writer: the Ansible primary-admin blueprint assigned `groups: [authentik Admins]` to existing users. Authentik replaces the entire membership relation, removing OpenTofu-owned All Applications and Forgejo Owners membership. This was reproduced locally against the pinned 2026.8.3 image and disposable PG17 database; health checks alone do not catch it.

Assign initial admin membership only in `state: created` entries. Continue reconciling primary-admin identity and recovery credentials through a separate present-state entry without `groups`. Existing memberships remain owned by OpenTofu, not periodically reset by the blueprint. The shared admin-reconciliation tasks snapshot and assert existing memberships on bearer-token deployments. `src/reconcile-authentik-admin.yml` enables a targeted repair without host activation or unrelated provider changes. Blueprint cleanup now fails on HTTP errors rather than silently retaining an enabled secret-bearing writer.

Regression coverage exercises repeated imports, two distinct identities, a shared primary-admin/scetrov identity, unrelated groups and fresh-admin bootstrap/password reconciliation. A pre-commit ownership guard rejects future present-state group assignments. This prevents the identified reset path; it cannot guarantee against all manual/API changes or future external writers. Browser OIDC smoke tests remain required.

### D8 — Cooldown bookkeeping

`tasks.md` records, for every bumped component: the version skipped by the cooldown (if any) and its release date, so a follow-up change can lift codex `0.162.1` and grafana provider `4.50.0` on/after 2026-10-14.

## Risks / Trade-offs

- [Postgres restore loses container-local extensions/roles not captured by `pg_dumpall`] → include `pg_dumpall -g` (global objects) and verify extension list (PostGIS etc.) before/after; keep cold data-dir copy as last resort.
- [Authentik 2026.5→2026.8 spans multiple release migrations and is the SSO gateway for the whole fleet] → stage as its own `--tags authentik` run, smoke-test OIDC login + Terraform `plan` (must be no-op) before continuing.
- [OnCall downtime during PG/Redis swap] → OnCall is a leaf service (alerting UI); accept minutes of downtime, schedule in one `--tags oncall` run.
- [Digest capture at implementation differs from design-time values (re-tagged images)] → re-resolve digests at implementation; any mismatch is a red flag that the upstream re-tagged — pause and investigate (possible supply-chain signal).
- [nixpkgs revision bump for codex pulls a newer toolchain for the image build] → build is hermetic in `pinnedNixpkgs` import; only the codex image is affected; assert block catches version drift.
- [Terraform provider 4.49.0 vs pinned 4.47.0 schema changes] → run `tofu plan` via `scripts/tofu.sh` and confirm no unexpected changes before `apply`.
- [7x7 rule interplay] → operator explicitly approved a one-time five-day exception for this change's reviewed frozen targets on 2026-10-14. The standing policy remains seven days; proactive maintenance alone is not an exemption.

## Migration Plan

1. Verify the migration helper locally against pinned PG16/PG17 containers; verify Ansible/shell syntax and pre-commit checks.
2. `play.sh --limit habiki --tags database-upgrade -- -e upgrade_confirm=true` — coordinated maintenance for the three databases and Redis, followed by the database-only and Authentik-image activation stages described in D4. This host-wide switch also activates the other Habiki image pins; they are not misleadingly treated as isolated component deployments.
3. Verify Forgejo and Dependency-Track OIDC. Run OpenTofu plans/apply only through `scripts/tofu.sh`; the Authentik Ansible role must use that wrapper too.
4. Deploy other actual inventory hosts only as needed with `--limit <host> --tags nixos`; there is no host named `home` in the inventory.
5. Watch Loki/Grafana after maintenance; any new error spike pauses sign-off.

**Rollback:** `scripts/play.sh --limit habiki --tags database-upgrade -- -e upgrade_confirm=true -e upgrade_action=rollback -e upgrade_backup_dir=/var/lib/component-upgrade/<run>`. This restores the previous NixOS generation and retained PG16 directories, plus the Redis snapshot. Repository pins remain new; the ordinary deployment preflight refuses another switch over restored PG16 data. Do not delete backups or the previous-generation GC root for at least 7 days.

## Open Questions

- None blocking. The only deferred items are the cooldown-gated versions (codex 0.162.1, grafana provider 4.50.0, home-assistant 2026.10.1) — revisit in a follow-up change after 2026-10-14.
