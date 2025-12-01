{ config, pkgs, ... }:

{
  services.synergy.client = {
    enable = true;
    serverAddress = "bullit";
    startOnBoot = true;
  };
}