{ config, pkgs, ... }:
let
  baseconfig = { allowUnfree = true; };
  unstable = import <nixos-unstable> { config = baseconfig; };
in {
  # List packages installed in system profile. To search, run:
  # $ nix search wget
  environment.systemPackages = with pkgs; [
    ansible
    gcc
    niv
    nixos-generators
    nodejs_18
    nodejs_18.pkgs.pnpm
    python3
    wget
    zsh
    (pkgs.callPackage <agenix/pkgs/agenix.nix> {})
  ];
}