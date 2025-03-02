{ config, ... }:

{
  services.xserver.enable = true;
  services.displayManager.sddm.enable = true;
  services.desktopManager.plasma6.enable = true;
  services.kde.kwallet.enable = true;

  services.xrdp.enable = true;
  services.xrdp.defaultWindowManager = "startplasma-x11";
  services.xrdp.openFirewall = true;

  security.pam.services.kwallet = {
    name = "kwallet";
    enableKwallet = true;
  };

  programs.chromium.enablePlasmaBrowserIntegration = true;

  services.xserver.xkb = {
    layout = "gb";
    variant = "";
  };
}
