{ config, pkgs, ... }:

{
  imports = [
    ./hardware-configuration.nix
    ./modules/defaults.nix
    ./modules/locale.nix
    ./modules/maintenance.nix
    ./modules/networking.nix
    ./modules/audio.nix
    ./modules/pkgs-unstable.nix
    ./modules/pkgs-latest.nix
    ./modules/programs.nix
    ./modules/security.nix
    ./modules/user-secetrov.nix
    ./modules/docker.nix
    ./modules/xserver.nix
  ];

  virtualisation.docker.enable = true;
  services.dockerRegistry.enableGarbageCollect = true;

  # This value determines the NixOS release from which the default
  # settings for stateful data, like file locations and database versions
  # on your system were taken. It‘s perfectly fine and recommended to leave
  # this value at the release version of the first install of this system.
  # Before changing this value read the documentation for this option
  # (e.g. man configuration.nix or on https://nixos.org/nixos/options.html).
  system.stateVersion = "24.11"; # Did you read the comment?
}
