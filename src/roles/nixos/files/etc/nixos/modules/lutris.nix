{ config, ... }:
let
  baseconfig = { allowUnfree = true; };
  unstable = import <nixos-unstable> { config = baseconfig; };
in {
  environment.systemPackages = with unstable; [
    lutris
    vulkan-tools
    winePackages.stableFull
  ];
}
