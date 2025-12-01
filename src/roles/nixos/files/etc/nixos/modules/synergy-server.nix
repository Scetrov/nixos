{ config, pkgs }:

{
  services.synergy.server = {
    enable = true;
    startOnBoot = true;
  };
}