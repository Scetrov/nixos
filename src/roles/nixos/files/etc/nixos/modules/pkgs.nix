{ config, pkgs, ... }:
let
  baseconfig = {
    allowUnfree = true;
  };
  unstable = import <nixos-unstable> { config = baseconfig; };
in
{
  nixpkgs.config.allowUnfree = true;

  environment.systemPackages =
    with pkgs;
    [
      ansible
      bat
      dig
      gcc
      go
      niv
      nixos-generators
      nodejs_24
      pnpm
      networkmanager-openvpn
      opentofu
      openvpn
      (python3.withPackages (ps: with ps; [ cryptography ]))
      wget
      (pkgs.callPackage <agenix/pkgs/agenix.nix> { })
    ]
    ++ pkgs.lib.optionals (pkgs.stdenv.hostPlatform.system == "x86_64-linux") [
      # SteamCMD ships only for x86_64; evaluating it on Fyne (aarch64) fails.
      steamcmd
    ];
}
