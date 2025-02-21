{ config, pkgs, ...}:

{
  system.autoUpgrade.enable = true;
  system.autoUpgrade.allowReboot = true;

  nix.gc.automatic = true;
}
