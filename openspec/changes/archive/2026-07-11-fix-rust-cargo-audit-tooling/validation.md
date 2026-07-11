# Validation Results

Validated on `bullit` after deployment with `./scripts/play.sh --limit bullit --tags nixos`.

- A fresh login shell reports Rust 1.97.0 from both `rustc --version` and `cargo --version`.
- `command -v rustc` and `command -v cargo` resolve through the deployed Nix profile, not `~/.rustup`.
- `cargo audit --version` succeeds using the declaratively installed `cargo-audit` executable.
- The previous stale-interpreter failure no longer reproduces.

Validation was confirmed by the operator on 2026-07-11.
