# Component Version Currency

## Purpose

Keep managed software on reviewed stable releases with immutable integrity anchors, compatible identity APIs and verified rollback for data migrations.

## Requirements

### Requirement: All managed container images are pinned to an explicit version tag
Every container image referenced in NixOS modules MUST use an explicit, non-floating version tag. The tags `:latest` and `:stable`, and channel-only tags (e.g. `2-alpine`, `16-alpine`, `pg17` without digest) MUST NOT be used as the sole reference for a deployed image.

#### Scenario: No floating tags in deployed modules
- **WHEN** the repository is scanned for container image references in `src/roles/nixos/files/etc/nixos/modules/*.nix`
- **THEN** every reference resolves to an explicit version tag (e.g. `2026.8.3`, `17-alpine`, `v1.16.11`, `2.11.7-alpine`)

#### Scenario: Documented exception for private registry
- **WHEN** an image is hosted on a registry not publicly resolvable (e.g. `nousresearch/hermes-agent`)
- **THEN** the reference carries a comment documenting the exception and the reason pinning is impossible from this environment

### Requirement: Public-registry images are anchored by sha256 digest
Every container image pulled from a public registry (Docker Hub or public GHCR) MUST be referenced in OCI form `registry/repo:tag@sha256:<digest>` where the digest is the multi-arch manifest index digest for that tag.

#### Scenario: Digest present on public images
- **WHEN** an image reference points at Docker Hub or a public GHCR repository
- **THEN** the reference contains an `@sha256:` suffix with a 64-character hex digest

#### Scenario: Digest mismatch blocks deployment
- **WHEN** the implementation-time digest resolved from the registry differs from the digest recorded in the change
- **THEN** the change MUST be paused and the discrepancy investigated as a potential re-tag or supply-chain signal before proceeding

### Requirement: Components are at the latest stable release that has passed the seven-day cooldown
As of the change date, every managed component MUST be at the newest applicable stable release published at least seven days before that date, unless the operator explicitly approves and records a scoped exception. Releases inside the applicable cooldown window MUST be explicitly recorded as deferred with their release date. The operator approved a one-time five-day exception for the reviewed, frozen targets in upgrade-components-latest-stable on 2026-10-14; this does not reduce the standing seven-day policy.

#### Scenario: Cooldown-deferred releases are recorded
- **WHEN** the newest stable release of a component was published less than the applicable cooldown before the change date
- **THEN** the component is pinned to the newest stable that HAS passed the window, and the deferred version with its release date is recorded in the change's task list

#### Scenario: Verified-current components are untouched
- **WHEN** a component's pinned version already equals the latest stable (e.g. Frontier Indexer `v0.4.0`, ESPHome `2026.9.1`)
- **THEN** the change MUST NOT modify that component

### Requirement: Authentik image and Terraform provider share one major line
The deployed Authentik server image and the `goauthentik/authentik` Terraform provider MUST target the same major release line so that the provider SDK contract matches the server API.

#### Scenario: Lines aligned after upgrade
- **WHEN** the upgrade is applied
- **THEN** the image is `2026.8.3` and the provider constraint remains `2026.8.0`-series (both on the 2026.8 line)

#### Scenario: Stale alignment comment removed
- **WHEN** `terraform/main.tf` is reviewed after the change
- **THEN** no comment references the superseded 2026.5 line as the deployment target

### Requirement: Database major upgrades use verified backups and a defined rollback
Major version upgrades of Postgres (16→17) and Redis (7→8) MUST be preceded by a verified backup and MUST define a rollback path that restores the previous version from that backup.

#### Scenario: Postgres upgrade step
- **WHEN** a component's Postgres image moves from `16-alpine` to `17-alpine`
- **THEN** a `pg_dumpall` capture (plus a cold data-directory copy) exists on the host before the data volume is replaced, and the restored database passes the component's health checks

#### Scenario: Rollback restores the previous major
- **WHEN** the upgraded component fails verification
- **THEN** the previous major's container is restarted against the pre-upgrade backup and the component's health checks pass

### Requirement: Terraform provider constraints do not float silently
Every Terraform provider in `terraform/main.tf` MUST have a constraint that pins at least the minor series, and provider bumps MUST be validated with a plan showing no unexpected resource changes before apply.

#### Scenario: Constraint granularity
- **WHEN** `terraform/main.tf` is reviewed
- **THEN** no provider uses a bare major constraint (e.g. `~> 3.0`) and each constraint matches the pinned series (grafana `4.49.0`, random exact `3.9.1`)

#### Scenario: Plan validation before apply
- **WHEN** a provider version changes
- **THEN** `scripts/tofu.sh` plan output is reviewed and contains no resource changes beyond the provider update before `apply` runs
