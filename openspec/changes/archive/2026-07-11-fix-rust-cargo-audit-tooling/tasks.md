## 1. Package Rust 1.97.0

- [x] 1.1 Select an immutable rust-overlay revision that exposes Rust 1.97.0 and record its verified fixed source hash
- [x] 1.2 Add a repository-managed Nix package expression selecting the Rust 1.97.0 toolchain with Cargo, rustfmt, and Clippy
- [x] 1.3 Evaluate or build the package expression and confirm its `rustc` and `cargo` binaries report version 1.97.0

## 2. Configure Developer Tooling

- [x] 2.1 Update `user-scetrov.nix` to replace `rustup` with the Nix-managed Rust 1.97.0 toolchain
- [x] 2.2 Add `unstable.cargo-audit` to the declarative user package set and confirm no wrapper or alias shadows it
- [x] 2.3 Format the changed Nix files and validate the affected NixOS configuration without deploying

## 3. Review and Deploy

- [x] 3.1 Review the diff and scan all changed files for secrets, generated state, dangling endpoints, or unrelated changes
- [x] 3.2 Stage the OpenSpec artifacts and implementation files required for commit
- [x] 3.3 Deploy the NixOS change with `./scripts/play.sh --limit bullit --tags nixos`

## 4. Verify the Environment

- [x] 4.1 In a fresh login shell, verify `rustc --version` and `cargo --version` both report 1.97.0
- [x] 4.2 Verify `command -v rustc` and `command -v cargo` resolve through the deployed Nix profile and not `~/.rustup`
- [x] 4.3 Verify `cargo audit --version` succeeds using the declaratively installed cargo-audit executable
- [x] 4.4 Record validation results and confirm the broken stale-interpreter behavior no longer reproduces
