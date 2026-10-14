{ pkgs }:

let
  rust-overlay = import (
    pkgs.fetchFromGitHub {
      owner = "oxalica";
      repo = "rust-overlay";
      rev = "f91010a5c1b6125b715eb78a84fb5dd8fb74a2b0";
      hash = "sha256-HJ4TEF3j7HmLYeEP/PtqjeiBX/6TppXB2qY53HcrWbs=";
    }
  );
  rustPkgs = pkgs.extend rust-overlay;
in
rustPkgs.rust-bin.stable."1.99.0".default.override {
  extensions = [
    "rustfmt"
    "clippy"
  ];
}
