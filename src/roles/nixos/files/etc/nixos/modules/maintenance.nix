{ config, ... }:

{
  system.autoUpgrade.enable = true;
  system.autoUpgrade.allowReboot = false;
  nix.gc = {
    automatic = true;
    dates = "weekly"; # or "daily"
    options = "--delete-older-than 14d"; # keep last 14 days of generations
  };
}
