## ADDED Requirements

### Requirement: Declarative Rust toolchain
The system SHALL provision Rust 1.97.0 and its matching Cargo tool through the repository-managed NixOS configuration for the `scetrov` developer environment, and SHALL keep the selected toolchain's runtime dependencies in the deployed Nix closure.

#### Scenario: Rust compiler version is available
- **WHEN** the targeted NixOS configuration has been deployed and the user starts a fresh login shell
- **THEN** `rustc --version` succeeds and reports Rust 1.97.0

#### Scenario: Matching Cargo version is available
- **WHEN** the targeted NixOS configuration has been deployed and the user starts a fresh login shell
- **THEN** `cargo --version` succeeds and reports Cargo 1.97.0

#### Scenario: Toolchain does not resolve through rustup
- **WHEN** the user resolves the active `rustc` and `cargo` commands after deployment
- **THEN** both commands resolve from the deployed Nix profile without depending on a toolchain under `~/.rustup`

### Requirement: Declarative Cargo audit command
The system SHALL provision `cargo-audit` through the repository-managed NixOS configuration so Cargo can invoke it as the `audit` subcommand without a per-user `cargo install` operation.

#### Scenario: Cargo audit is discoverable
- **WHEN** the targeted NixOS configuration has been deployed and the user runs `cargo audit --version`
- **THEN** the command succeeds and reports the installed cargo-audit version

#### Scenario: Audit execution without a Rust workspace
- **WHEN** validation occurs in this infrastructure repository, which has no Cargo manifest or lockfile
- **THEN** validation uses the cargo-audit version command and does not require a dependency audit to complete

### Requirement: Rust tooling change validation
The system MUST validate the Nix configuration before deployment and MUST verify tool versions and command resolution after a targeted deployment.

#### Scenario: Configuration is invalid
- **WHEN** the pinned Rust package source, overlay selection, or user module fails Nix evaluation or build validation
- **THEN** deployment is blocked until the error is corrected

#### Scenario: Post-deployment tooling validation
- **WHEN** the NixOS deployment to the affected host completes
- **THEN** validation confirms Rust 1.97.0, Cargo 1.97.0, a working cargo-audit version command, and Nix-profile command resolution
