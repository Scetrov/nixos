{ config, pkgs, ... }:

{
  imports = [
    ./device-configuration.nix
    ./hardware-configuration.nix
    ./modules/audio.nix
    ./modules/locale.nix
    ./modules/maintenance.nix
    ./modules/networking.nix
    ./modules/pkgs.nix
    ./modules/podman.nix
    ./modules/programs.nix
    ./modules/security.nix
    ./modules/user-scetrov.nix
    ./modules/zsh.nix
    <agenix/modules/age.nix>
  ];

  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;
  nixpkgs.config.allowUnfree = true;

  # This value determines the NixOS release from which the default
  # settings for stateful data, like file locations and database versions
  # on your system were taken. It‘s perfectly fine and recommended to leave
  # this value at the release version of the first install of this system.
  # Before changing this value read the documentation for this option
  # (e.g. man configuration.nix or on https://nixos.org/nixos/options.html).
  system.stateVersion = "24.11"; # Did you read the comment?
}
