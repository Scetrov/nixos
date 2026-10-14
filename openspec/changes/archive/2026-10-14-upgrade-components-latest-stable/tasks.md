## 1. Re-verify digests and versions (supply-chain gate)

- [x] 1.1 Re-resolve every tag→digest pair from design.md D1 against the registries (Docker Hub token flow, GHCR token flow); any digest that differs from the recorded value stops the change for investigation _(verified 2026-10-14: all 12 tag→digest pairs re-resolve to their recorded values; `timescale/timescaledb-ha:pg17` lives on Docker Hub, not GHCR — 20534b8a… matches)_
- [x] 1.2 Confirm no newer eligible stable appeared since 2026-10-14 for any target (re-run the version review; update targets only if a newer release has passed the 5-day cooldown) _(verified 2026-10-14: implementation is same-day as design freeze; independent re-review of registry tag lists confirms every target is newest-in-line or newest-passing-cooldown. DT `5.x` major and Postgres `18` remain deliberate major non-goals.)_
- [x] 1.3 Confirm cooldown-deferred versions stay deferred: codex `0.162.1` (2026-10-09), grafana provider `4.50.0` (2026-10-14), home-assistant `2026.10.1` (2026-10-10) _(verified 2026-10-14: codex 0.162.1 npm publish = 2026-10-09T19:50Z, only 4d21h old → 120h cooldown completes 2026-10-14T19:50Z, not yet passed → stays 0.162.0. grafana 4.50.0 = 0 days, HA 2026.10.1 = ~4 days → both stay deferred.)_

## 2. Image pin bumps with digests (NixOS modules)

- [x] 2.1 `home-assistant.nix`: `ghcr.io/home-assistant/home-assistant:stable` → `2026.10.0@sha256:1b64d38f38d922bf9d59336451fd6453e1d614f934456af4ee3d2a51061be3a4`
- [x] 2.2 `home-assistant.nix`: `matterServerImage` → `ghcr.io/matter-js/python-matter-server:8.1.2@sha256:6827e352011e2d8c2bde771e446fcf72acc49150ef66bad978816bac1762aad3`
- [x] 2.3 `oncall.nix`: all three `docker.io/grafana/oncall:latest` refs → `v1.16.11@sha256:9abc7342e10022da5893867789a91112fe366b3cd064a07a32d752f9de395fe5`
- [x] 2.4 `grafana-mcp.nix`: `docker.io/grafana/mcp-grafana:latest` → `2.0.2@sha256:78d208116ec52b09b44f0eca66892073b39aefcb64483c54d43255c8eab7e97a`
- [x] 2.5 `hermes.nix`: caddy default → `caddy:2.11.7-alpine@sha256:d8542f48d34a9cf4e4c11a478865229840e87e4c96ea3f439101f31a5d35f75f`; hermes-webui → `latest@sha256:5fb831ca2a9f3f0b93b84c1ebaaeedf5809d914a33bbf969e5c29a5bb75cb47c` with documented exception comment on `nousresearch/hermes-agent:latest`
- [x] 2.6 `frontier-indexer.nix`: `timescaledb-ha:pg17` → `pg17@sha256:20534b8a06680956336604f3735d5811807f5244c6a364c761a70dea9c63de36` with comment explaining digest-anchored floating tag (tag list not enumerable)
- [x] 2.7 `dependency-track.nix`: apiserver + frontend → `4.14.5@sha256:4d41f29ce886a7fcb94a424b3eb2bfd17497ba92d48d43896c48e87a69bcf335` / `4.14.5@sha256:d675efbd80facddb696c21c82e1973d0dc83ae38b3c896d1c87bf78a26a6c9eb`

## 3. Postgres 16→17 / Redis 7→8 data migrations (habiki, backup-first)

- [x] 3.0 Repair the deployment assumptions with one explicit Ansible maintenance playbook, a pre-PG17 activation guard, named Redis persistence and an explicit rollback; validate the restore locally with pinned PG16/PG17 containers. Component tags do not isolate NixOS switches (see revised D4).

- [x] 3.1 OnCall: snapshot `dump.rdb`, `pg_dumpall` + cold data-dir copy of the oncall Postgres 16 volume _(2026-10-14: verified isolated restore; host backups under `/var/lib/component-upgrade/20261014T175136`)_
- [x] 3.2 OnCall: bump `oncall.nix` Postgres → `postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24`, Redis → `redis:8-alpine@sha256:3811787313eba226a2ef38658c6ccb91cd5e110edc89c37767de373120a0e5a0`; deploy through the coordinated `./scripts/play.sh --limit habiki --tags database-upgrade -- -e upgrade_confirm=true` maintenance run; restore dump into the fresh 17 initdb; verify OnCall health checks
- [x] 3.3 Dependency-Track: `pg_dumpall` + cold copy of its Postgres 16 volume; bump `dependency-track.nix` Postgres → `17-alpine` (same digest); deploy through the same coordinated maintenance run (not a separate component-tagged rebuild); restore + verify DT API health
- [x] 3.4 Authentik: `pg_dumpall` (incl. `-g` globals) + cold copy; bump `authentik.nix` Postgres → `17-alpine`; activate the maintenance playbook's database-only stage with the running 2026.5 image digest first, verify restore; then task 4.1
- [x] 3.5 Keep all step-3 backups on the host for ≥ 7 days; record backup locations in the PR description _(root-only backup directory, dumps/cold copies, retained originals and previous-generation GC root verified present after final deployment; PR body records minimum retention until 2026-10-21 17:51:36 UTC; no cleanup is scheduled. The seven-day period is still in progress.)_

## 4. Authentik 2026.5 → 2026.8.3

- [x] 4.1 `authentik.nix`: server image → `ghcr.io/goauthentik/server:2026.8.3@sha256:ab9b4e8cc4ab3f8d1198d2db6aeea66bafea1963b3f2843589e0d163f97d9849`; deploy; let 2026.8 migrations run _(2026-10-14: resumed prepared run `/var/lib/component-upgrade/20261014T175136`; Ansible failed=0, migrations applied, all three application health checks returned 200, no failed systemd units, temporary stage removed; controller log `/tmp/nixos-authentik-resume.log`)_
- [x] 4.2 Smoke-test OIDC login for at least two integrations (Forgejo + Dependency-Track SSO) _(2026-10-14: user reported denial and missing assigned applications. Read-only live policy probe reproduced both denials: `scetrov` was absent from the empty All Applications and Forgejo Owners groups. Targeted `scripts/tofu.sh` plan/apply restored declared user 9 membership in both groups, with only two in-place changes. Uncached policy evaluation now passes for both applications; user confirmed both browser SSO logins are accessible after the repair. Root cause subsequently reproduced with the pinned Authentik importer: the primary-admin blueprint's present-state `groups` assignment replaces application memberships. Fixed with creation-only admin-group bootstrap, preserving steady-state identity/password reconciliation. Targeted Ansible repair deployed successfully, membership preservation assertions passed, and the stale `ansible-primary-admin` instance was removed. Both uncached application policies still pass.)_
- [x] 4.3 Rewrite the stale 2026.5 comment block in `terraform/main.tf` to state the 2026.8 line alignment rationale; run `scripts/tofu.sh` plan and confirm no unexpected changes _(full-root plan exit 0, zero changes after operator-approved configuration alignment for new authorization redirect defaults and CSS trailing whitespace)_
- [x] 4.4 Verify `tofu apply` is clean (or no-op) with the 2026.8.3 server live _(wrapper apply exit 0: 0 added, 0 changed, 0 destroyed; encrypted generated secrets refreshed)_

## 5. Toolchain bumps

- [x] 5.1 Codex: find a nixpkgs master commit (≥ 5 days old) whose `pkgs/by-name/co/codex/package.nix` builds `0.162.0`; update `codex-app-server-image.nix` (`codexVersion`, `nixpkgsRevision`, `nixpkgsHash`, `codexSourceHash`, `codexCargoHash`); confirm all assertions pass on build
- [x] 5.2 Codex: update `ai-usage.nix` default `codex-app-server:0.145.0` → `codex-app-server:0.162.0` and `tests/ai-usage-eval.nix` container image assertion in lockstep
- [x] 5.3 Rust: bump rust-overlay rev+hash to a pinned rev containing stable `1.99.0`; change attrset key to `"1.99.0"`; rename `pkgs/rust-1_97.nix` → `rust-1_99.nix`; update import in `user-scetrov.nix`
- [x] 5.4 `.pre-commit-config.yaml`: `pre-commit-hooks` `v5.0.0` → `v6.0.0`; run `pre-commit run -a` and fix any new findings _(v6.0.0 anchored to commit `3e8a8703264a2f4a69428a0aa4dcb512790b2c8c`; all checks passed)_

## 6. Terraform provider bumps

- [x] 6.1 `terraform/main.tf`: `grafana/grafana` `4.47.0` → `4.49.0`; `hashicorp/random` `~> 3.0` → exact `3.9.1` _(operator selected exact pin to prevent later 3.x minor drift)_
- [x] 6.2 Run `scripts/tofu.sh` plan for every module; confirm zero unexpected resource changes; record the cooldown-deferred `4.50.0` (2026-10-14) as a follow-up _(single Terraform root covers all managed resources; full plan exit 0 with grafana 4.49.0 and exact random 3.9.1; grafana 4.50.0 remains deferred)_

## 7. Verification and sign-off

- [x] 7.1 `nixos-rebuild`/`play.sh --tags nixos` passes on a target host for every touched module (lint + eval) _(2026-10-14: targeted `scripts/play.sh --limit habiki --tags nixos` completed with failed=0; Habiki enables all touched service modules and common user/toolchain configuration; controller log `/tmp/nixos-component-final-deploy.log`)_
- [x] 7.2 Repost the full version table (pinned → target → digest → deferred) in the PR body _(complete table and backup/rollback evidence prepared in `pr-body.md` for publication with task 7.5)_
- [x] 7.3 Grep audit: no unanchored floating image literals except the documented private Hermes agent; versionless Hermes WebUI and channel-only TimescaleDB/Postgres/Redis references are digest-anchored as allowed by the design _(2026-10-14: all module literals audited; no `:stable` remains)_
- [x] 7.4 Check the AGENTS.md sign-off checklist (staging, no secrets, local DNS, IdAM, observability, hygiene, concurrency, 7x7) _(all scoped changes staged; gitleaks/pre-commit pass; no new DNS aliases or public endpoints; Authentik remains IdAM; Loki and application health reviewed; reviewed immutable inputs and explicit registry exceptions recorded. Operator approved a one-time five-day cooldown exception for frozen targets; standing policy remains seven days.)_
- [ ] 7.5 Create the PR with a signed commit (Conventional Commit + Agent/Model Co-Authored-By trailers)
