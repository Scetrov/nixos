{ config, pkgs, ... }:
let
  baseconfig = { allowUnfree = true; };
  unstable = import <nixos-unstable> { config = baseconfig; };
in {
  nixpkgs.config.allowUnfree = true;
  
  # $ nix search wget
  environment.systemPackages = with pkgs; [
    ansible
    bat
    gcc
    niv
    nixos-generators
    nodejs_18
    nodejs_18.pkgs.pnpm
    networkmanager-openvpn
    openvpn
    (python3.withPackages (ps: with ps; [ cryptography ]))
    wget
    (pkgs.callPackage <agenix/pkgs/agenix.nix> {})
  ];
}