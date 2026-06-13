{ config, pkgs, ... }:

let
  xrdpPlasmaSession = pkgs.writeShellScript "xrdp-startplasma-x11" ''
    export XDG_SESSION_TYPE=x11
    export DESKTOP_SESSION=plasma
    export KDE_SESSION_VERSION=6

    unset QT_SCREEN_SCALE_FACTORS
    unset QT_SCALE_FACTOR
    unset KSCREEN_BACKEND

    export KWIN_COMPOSE=N

    if command -v kwriteconfig6 >/dev/null 2>&1; then
      kwriteconfig6 --file kdeglobals --group KScreen --key ScaleFactor --delete || true
      kwriteconfig6 --file kdeglobals --group KScreen --key ScreenScaleFactors --delete || true
      kwriteconfig6 --file kwinrc --group Compositing --key Enabled false || true
    fi

    rm -rf "$HOME/.local/share/kscreen"

    exec ${pkgs.kdePackages.plasma-workspace}/bin/startplasma-x11
  '';
in
{
  services.xserver.enable = true;
  services.displayManager.sddm.enable = true;
  services.desktopManager.plasma6.enable = true;

  services.xrdp = {
    enable = true;
    openFirewall = true;
    defaultWindowManager = "${xrdpPlasmaSession}";
  };

  security.pam.services.kwallet = {
    name = "kwallet";
    enableKwallet = true;
  };

  programs.chromium.enablePlasmaBrowserIntegration = true;

  services.xserver.xkb = {
    layout = "gb";
    variant = "";
  };

  environment.plasma6.excludePackages = with pkgs.kdePackages; [
    konsole
    kate
    elisa
  ];
}
