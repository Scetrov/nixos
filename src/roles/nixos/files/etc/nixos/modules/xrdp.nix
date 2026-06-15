{ config, pkgs, ... }:

let
  xrdpPlasmaSession = pkgs.writeShellScript "xrdp-startplasma-x11" ''
    export XDG_SESSION_TYPE=x11
    export DESKTOP_SESSION=plasma
    export KDE_SESSION_VERSION=6
    export XDG_CURRENT_DESKTOP=KDE
    export XDG_SESSION_DESKTOP=KDE
    export QT_QPA_PLATFORM=xcb

    # Avoid inheriting local-session scaling into the xrdp session.
    unset QT_SCREEN_SCALE_FACTORS
    unset QT_SCALE_FACTOR
    unset KSCREEN_BACKEND

    # xrdp usually has no useful GPU acceleration.
    # Software OpenGL gives KWin a better chance of enabling compositing cleanly.
    export LIBGL_ALWAYS_SOFTWARE=1

    # Do not force compositing off. O2 = OpenGL 2 compositing.
    export KWIN_COMPOSE=O2

    if command -v kwriteconfig6 >/dev/null 2>&1; then
      # Keep your existing scaling fix.
      kwriteconfig6 --file kdeglobals --group KScreen --key ScaleFactor --delete || true
      kwriteconfig6 --file kdeglobals --group KScreen --key ScreenScaleFactors --delete || true

      # Keep KWin compositing enabled in the xrdp session.
      kwriteconfig6 --file kwinrc --group Compositing --key Enabled true || true
      kwriteconfig6 --file kwinrc --group Compositing --key OpenGLIsUnsafe false || true

      # Use Breeze decorations, but remove the visible window border.
      kwriteconfig6 --file kwinrc --group org.kde.kdecoration2 --key library org.kde.breeze || true
      kwriteconfig6 --file kwinrc --group org.kde.kdecoration2 --key theme Breeze || true
      kwriteconfig6 --file kwinrc --group org.kde.kdecoration2 --key BorderSize None || true
    fi

    rm -rf "$HOME/.local/share/kscreen"

    exec ${pkgs.dbus}/bin/dbus-run-session ${pkgs.kdePackages.plasma-workspace}/bin/startplasma-x11
  '';
in
{
  services.xserver.enable = true;
  services.displayManager.sddm.enable = true;
  services.desktopManager.plasma6.enable = true;

  environment.systemPackages = with pkgs; [
    kdePackages.kconfig
    kdePackages.kdbusaddons
    kdePackages.qttools
  ];

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
