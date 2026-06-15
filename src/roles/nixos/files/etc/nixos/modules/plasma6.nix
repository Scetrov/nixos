{ config, pkgs, ... }:
{
  environment.plasma6.excludePackages = with pkgs.kdePackages; [
    konsole
    kate
    elisa
    xterm
  ];
}
