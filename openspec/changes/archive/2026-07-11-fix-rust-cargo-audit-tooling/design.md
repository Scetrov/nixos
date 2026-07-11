## Context

`user-scetrov.nix` currently installs Nixpkgs `rustup`. Its `cargo` executable is a rustup proxy, while downloaded toolchain binaries are patched to a concrete Nix-store glibc interpreter. After that interpreter was garbage-collected, the proxy continued to resolve the toolchain but could no longer execute `cargo` or `rustc`. The environment also lacks the standalone `cargo-audit` executable that Cargo needs to resolve `cargo audit`.

The current `nixos-unstable` channel provides Rust 1.95.0 rather than the requested 1.97.0, so selecting `unstable.rustc` cannot meet the version requirement. Configuration must remain declarative and deploy through the existing NixOS/Ansible workflow.

## Goals / Non-Goals

**Goals:**

- Make Rust 1.97.0, Cargo 1.97.0, rustfmt, and Clippy available from Nix-managed paths.
- Make `cargo audit` available through a declaratively installed `cargo-audit` executable.
- Eliminate the default developer toolchain's dependence on mutable rustup state under the user's home directory.
- Provide evaluation and post-deployment checks that expose version or command-resolution regressions.

**Non-Goals:**

- Manage project-specific Rust versions or targets.
- Preserve rustup as the default global toolchain manager.
- Add Cargo manifests or run dependency audits in this infrastructure repository, which contains no Rust workspace.
- Automate upgrades beyond the explicitly selected 1.97.0 release.

## Decisions

### Use a pinned rust-overlay source for Rust 1.97.0

Add a small package expression under the repository-managed Nix package directory that imports a pinned revision of `oxalica/rust-overlay` with a fixed source hash and selects the binary Rust 1.97.0 toolchain. Include Cargo, rustc, rustfmt, and Clippy components. Install that package from `user-scetrov.nix` instead of `rustup`.

This keeps the compiler and its interpreter closure in the Nix system profile, so garbage collection cannot remove a runtime dependency while the toolchain remains configured. It also achieves the exact requested version before the repository's `nixos-unstable` channel catches up.

Alternatives considered:

- Keep rustup and install/set 1.97.0 during activation. Rejected because it retains mutable per-user state and repeats the stale-interpreter failure mode.
- Use `unstable.rustc` and `unstable.cargo`. Rejected because the configured channel currently exposes 1.95.0.
- Package upstream Rust archives directly. Rejected because rust-overlay already encapsulates component assembly, target metadata, and Nix runtime patching.

### Install cargo-audit from nixos-unstable

Add `unstable.cargo-audit` to the user's declarative package list. Cargo discovers subcommands named `cargo-<name>` on `PATH`, so no wrapper or alias is necessary for `cargo audit`.

A Cargo-installed copy is not used because `cargo install` is imperative, compiles a duplicate local artifact, and leaves updates outside the NixOS deployment lifecycle.

### Remove rustup from the default user package set

Remove the Nixpkgs `rustup` package to prevent its proxy symlinks from winning command resolution over the Nix-managed Rust 1.97.0 binaries. Existing `~/.rustup` data may remain inert; deleting user data is unnecessary and would make rollback harder.

### Validate command identity and versions

Before deployment, evaluate/build the affected NixOS configuration sufficiently to catch source hash, overlay API, package, and module errors. After a targeted deployment to `bullit`, validate:

- `rustc --version` reports 1.97.0.
- `cargo --version` reports 1.97.0.
- `cargo audit --version` resolves successfully and reports the Nixpkgs package version.
- `command -v cargo` and `command -v rustc` resolve through the deployed Nix profile rather than rustup state.

Running an actual dependency audit is not a valid repository-level acceptance test because this repository has no `Cargo.toml` or `Cargo.lock`.

## Risks / Trade-offs

- **Pinned overlay source becomes an additional supply-chain dependency** → Pin an immutable revision and fixed hash; record the selected Rust version in the package expression and review future updates explicitly.
- **rust-overlay interface or component naming differs at the selected revision** → Evaluate and build before deployment, and keep the package expression isolated from the user module.
- **Removing rustup disrupts ad hoc multi-toolchain workflows** → Keep existing home-directory state untouched so rustup can be reintroduced deliberately if project-specific requirements emerge.
- **The 7x7 update rule could defer a non-security version update** → Treat restoring broken `cargo` and enabling security auditing as the justification for immediate deployment; document validation evidence.
- **`cargo-audit` may later require a newer compiler only when built from source** → Use the prebuilt Nix derivation and validate the executable rather than coupling it to the selected user compiler.

## Migration Plan

1. Add the pinned Rust 1.97.0 Nix package expression and reference it from `user-scetrov.nix`.
2. Replace `rustup` with the exact toolchain and add `unstable.cargo-audit`.
3. Format and evaluate the changed Nix expressions, then build/check the affected host configuration where practical.
4. Stage the reviewed artifact and implementation files, checking that no generated state or secrets are included.
5. Deploy through `./scripts/play.sh --limit bullit --tags nixos`.
6. Start a fresh login shell and run the command-resolution and version checks.

Rollback consists of reverting the package-list changes, redeploying the same targeted NixOS flow, and temporarily restoring rustup only if the previous behavior is explicitly desired.

## Open Questions

None. The exact rust-overlay revision and fixed source hash will be selected and verified during implementation.
