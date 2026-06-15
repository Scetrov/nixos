{ config, pkgs, ... }:
{
  environment.plasma6.excludePackages = with pkgs.kdePackages; [
    konsole
    kate
    elisa
  ];

  # Remove xterm from the X11 server default packages
  services.xserver.excludePackages = [ pkgs.xterm ];
}
