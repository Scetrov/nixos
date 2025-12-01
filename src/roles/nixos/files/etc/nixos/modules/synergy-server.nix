{ config, pkgs, ... }:

{
  services.synergy.server = {
    enable = true;
    autoStart = true;
  };
}