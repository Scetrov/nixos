{ config, pkgs, ... }:
let
  baseconfig = { allowUnfree = true; };
  unstable = import <nixos-unstable> { config = baseconfig; };
in {
  # List packages installed in system profile. To search, run:
  # $ nix search wget
  environment.systemPackages = with pkgs; [
    ansible
    bat
    gcc
    niv
    nixos-generators
    nodejs_18
    nodejs_18.pkgs.pnpm
    python3
    wget
    (pkgs.callPackage <agenix/pkgs/agenix.nix> {})
  ];
}