## Why

A review of every pinned software component (2026-10-14) found that most services in this fleet are behind the latest stable release, several images float on `:latest`/`:stable` tags with no supply-chain pinning, and the Authentik image/provider pair is split across incompatible major lines. This change brings every component to the latest stable release that has passed the 5-day supply-chain cooldown and replaces floating tags with explicit, digest-pinned references where the registry allows it.

## What Changes

Version bumps (all targets are latest stable as of 2026-10-14 that released ≥ 5 days before the change date):

- **Codex app-server**: `0.145.0` → `0.162.0` (0.162.1 released 2026-10-09, still inside the 5-day cooldown — explicitly deferred).
- **Rust toolchain**: `1.97.0` → `1.99.0` (channel 2026-10-01).
- **pre-commit-hooks**: `v5.0.0` → `v6.0.0` (2025-08-09).
- **Authentik server image**: `2026.5` → `2026.8.3` (2026-09-17). **BREAKING**: aligns the image with the already-deployed `2026.8.0` Terraform provider; database migration runs on the 2026.8 image and the 2026.5 SDK contract (pre-`pbm_uuid`) is dropped.
- **Dependency-Track api+frontend**: `4.14.1` → `4.14.5` (2026-10-05, same minor line — no migration). The `5.2.0` major is out of scope; tracked as follow-up.
- **Postgres**: `16-alpine` → `17-alpine` for Authentik and Dependency-Track (major upgrade requires a dump/restore migration). OnCall's Postgres is bumped `16-alpine` → `17-alpine` in the same migration pattern.
- **Redis**: `7-alpine` → `8-alpine` (OnCall; RDB format 7→8 is read-compatible but a backup is taken first).
- **Terraform providers**: `grafana/grafana` `4.47.0` → `4.49.0` (4.50.0 released 2026-10-14, in cooldown — deferred). `hashicorp/random` constraint tightened from `~> 3.0` to exact `3.9.1` to stop silent drift (operator-selected correction: `~> 3.9` would still permit later 3.x minors).

Pinning hardening (supply-chain / OWASP A03):

- Replace floating container tags with explicit version tags: `home-assistant:stable` → `2026.10.0`, `python-matter-server:stable` → `8.1.2`, `grafana/oncall:latest` → `1.16.11`, `grafana/mcp-grafana:latest` → `2.0.2`, `caddy:2-alpine` → `2.11.7-alpine`, `timescaledb-ha:pg17` → `pg17-ts2.30.2-p1` (or the exact published equivalent).
- Add `@sha256:` digests to every image that resolves from a public registry, matching the existing `frontier-indexer` pattern. `nousresearch/hermes-agent` and `ghcr.io/nesquena/hermes-webui` remain exception items (private registry, unresolvable from here) and are pinned to the most recently observed digest.

Not changed (verified current or unverifiable): Frontier Indexer `v0.4.0@sha256`, ESPHome `2026.9.1`, `goauthentik/authentik` provider `2026.8.0`, `conradludgate/caddy` provider `0.2.8`, `google-antigravity-cli`, OpenTofu (nixpkgs), NixOS channel.

## Capabilities

### New Capabilities

- `component-version-currency`: defines the standing policy that every managed component (container images, toolchain, Terraform providers) is pinned to an explicit version, kept at the latest stable release that has passed the 5-day cooldown, and anchored by a sha256 digest where the registry is public.

### Modified Capabilities

<!-- None: no existing spec's requirements change. Version pins for
     home-assistant-platform, codex-app-server-runtime, etc. are
     implementation details owned by those specs' deployments; the
     currency policy itself is new. -->

## Impact

- **Hosts**: habiki (Authentik, Dependency-Track, Frontier Indexer, Hermes, OnCall, Grafana MCP), fyne and any host running Home Assistant / Matter / Rust toolchain / pre-commit.
- **Data migrations**: Postgres 16→17 (Authentik, Dependency-Track, OnCall) and Redis 7→8 (OnCall) require dump/restore or backup/restore steps — this is the highest-risk part of the change.
- **Terraform**: provider bump of `grafana/grafana`; no state changes expected beyond provider schema validation.
- **CI/local dev**: Rust 1.97→1.99 and codex 0.145.0→0.162.0 affect the local toolchain and the codex app-server image rebuild; codex version assertion in `codex-app-server-image.nix` must move in lockstep.
- **Rollback**: each component rolls back independently by reverting its pin; Postgres/Redis rollback uses pre-upgrade backups.
