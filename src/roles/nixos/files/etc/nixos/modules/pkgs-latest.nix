{ config, pkgs, ... }:
let
  baseconfig = { allowUnfree = true; };
in {
  # List packages installed in system profile. To search, run:
  # $ nix search wget
  environment.systemPackages = with pkgs; [
    ansible
    gcc
    niv
    nodejs_18
    nodejs_18.pkgs.pnpm
    python3
    wget
    zsh
  ];
}