{ config, ... }:
let
  baseconfig = { allowUnfree = true; };
  unstable = import <nixos-unstable> { config = baseconfig; };
in {
  environment.systemPackages = with unstable; [
    devenv
    framesh
    ghostty
    brave
    obsidian
    hugo
    waypipe
  ];
}
