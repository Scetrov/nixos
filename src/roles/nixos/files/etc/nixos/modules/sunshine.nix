{
  config,
  pkgs,
  lib,
  ...
}:

{
  # ── Sunshine: host for Moonlight (remote desktop / game streaming) ──────────
  services.sunshine = {
    enable = true;
    autoStart = true;

    # Opens the Sunshine/Moonlight ports in the local NixOS firewall.
    # Still prefer using LAN/VPN only rather than exposing this to the internet.
    openFirewall = true;

    # capSysAdmin gives Sunshine CAP_SYS_ADMIN at runtime, which is commonly
    # required for Wayland/KMS capture paths (e.g. KMS, pipewire, or VA-API
    # encoding under NixOS).  Try without it first on X11-only setups.
    capSysAdmin = true;
  };

  # ── uinput: virtual input device for mouse/keyboard injection ──────────────
  # Sunshine uses /dev/uinput to inject mouse clicks, pointer movement, and
  # keyboard input into the host session.  Without this the streamed desktop
  # will be view-only.
  hardware.uinput.enable = true;

  # Add the desktop user to the uinput group so Sunshine's process can open
  # /dev/uinput for input injection.
  #
  # Note: we intentionally avoid adding the user to the broader "input" group
  # here because input grants read access to ALL input event devices
  # (/dev/input/event*), which is a wider trust boundary than uinput alone.
  # If mouse input still doesn't work after reboot, check logs first and
  # only add the user to the input group as a last resort.
  users.users.scetrov = lib.mkIf config.services.sunshine.enable {
    extraGroups = [ "uinput" ];
  };

  # ── Moonlight client (for testing from the same machine or another host) ────
  environment.systemPackages = with pkgs; [
    moonlight-qt
  ];
}
