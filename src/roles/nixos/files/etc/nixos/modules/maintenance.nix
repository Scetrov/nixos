{ config, ... }:

{
  system.autoUpgrade.enable = true;
  system.autoUpgrade.allowReboot = false;
  nix.gc.automatic = true;
}
