{ pkgs, lib, ... }:

{
  environment.systemPackages = [
    pkgs.yubikey-manager
  ];
}
