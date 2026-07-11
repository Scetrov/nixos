## Why

The managed development environment exposes a `cargo` proxy backed by Rust toolchains whose Nix store interpreter has been garbage-collected, while `cargo-audit` is not installed at all. Rust 1.97.0 is now available and provides a timely baseline for restoring a reproducible, working Rust security-audit workflow.

## What Changes

- Update the managed Rust toolchain baseline to Rust 1.97.0.
- Install `cargo-audit` declaratively so `cargo audit` is available without an imperative per-user Cargo installation.
- Define validation for the Rust compiler, Cargo, and Cargo audit commands after deployment.
- Avoid relying on stale, garbage-collectable interpreter references from previously downloaded rustup toolchains.

## Capabilities

### New Capabilities

- `developer-rust-tooling`: Defines the declaratively managed Rust toolchain version, Cargo audit availability, and post-deployment validation behavior for developer hosts.

### Modified Capabilities

None.

## Impact

- Affects `src/roles/nixos/files/etc/nixos/modules/user-scetrov.nix` and potentially a small supporting Nix package or activation configuration if rustup toolchain selection cannot be expressed safely inline.
- Adds the Nixpkgs `cargo-audit` package to the user environment.
- Changes the default Rust compiler and Cargo version available to the `scetrov` user to 1.97.0.
- Requires a targeted NixOS deployment and command-level validation on the affected host; no service ports, secrets, identity configuration, or external APIs are involved.
