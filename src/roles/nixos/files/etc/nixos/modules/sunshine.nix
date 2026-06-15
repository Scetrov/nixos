{ config, pkgs, ... }:

{
  services.sunshine = {
    enable = true;
    autoStart = true;

    # Opens the Sunshine/Moonlight ports in the local NixOS firewall.
    # Still prefer using LAN/VPN only rather than exposing this to the internet.
    openFirewall = true;

    # Commonly needed for Wayland capture on NixOS.
    # For X11-only testing you can try without it.
    capSysAdmin = true;
  };

  environment.systemPackages = with pkgs; [
    moonlight-qt
  ];
}
