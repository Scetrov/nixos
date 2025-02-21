{ config, ...}:
{
  services.xserver.enable = true;
  services.displayManager.sddm.enable = true;
  services.desktopManager.plasma6.enable = true;

  services.xrdp.enable = true;
  services.xrdp.defaultWindowManager = "startplasma-x11";
  services.xrdp.openFirewall = true;

  services.displayManager.autoLogin.enable = false;
  services.displayManager.autoLogin.user = "scetrov";
  
  programs.chromium.enablePlasmaBrowserIntegration = true;
}