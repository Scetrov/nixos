{ config, pkgs, ... }:

{
  services.xrdp.enable = false;

  services.displayManager.sddm.enable = true;
  services.desktopManager.plasma6.enable = true;

  environment.systemPackages = with pkgs; [
    kdePackages.krdp
    kdePackages.krdc # optional local RDP client
  ];
}
