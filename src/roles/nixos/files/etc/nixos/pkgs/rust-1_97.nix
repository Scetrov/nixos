{ pkgs }:

let
  rust-overlay = import (
    pkgs.fetchFromGitHub {
      owner = "oxalica";
      repo = "rust-overlay";
      rev = "e598b37857b895b81020a65a802ef55f5bbed72f";
      hash = "sha256-KlepQu/O5m11lAjcJ4ER5bc6bIzyX2UMPDARzMzQfIw=";
    }
  );
  rustPkgs = pkgs.extend rust-overlay;
in
rustPkgs.rust-bin.stable."1.97.0".default.override {
  extensions = [
    "rustfmt"
    "clippy"
  ];
}
