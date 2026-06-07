{ config, pkgs, ... }:
let
  baseconfig = {
    allowUnfree = true;
  };
  unstable = import <nixos-unstable> { config = baseconfig; };
in
{
  nixpkgs.config.allowUnfree = true;

  environment.systemPackages = with pkgs; [
    ansible
    bat
    dig
    gcc
    go
    niv
    nixos-generators
    nodejs_24
    nodejs_24.pkgs.pnpm
    networkmanager-openvpn
    opentofu
    openvpn
    (python3.withPackages (ps: with ps; [ cryptography ]))
    wget
    (pkgs.callPackage <agenix/pkgs/agenix.nix> { })
  ];
}
