{ config, pkgs, ... }:

{
  services.synergy.client = {
    enable = true;
    serverAddress = "bullit";
    autoStart = true;
  };
}