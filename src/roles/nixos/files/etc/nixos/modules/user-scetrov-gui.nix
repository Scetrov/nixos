{ config, pkgs, ... }:
let
  baseconfig = {
    allowUnfree = true;
  };
  unstable = import <nixos-unstable> { config = baseconfig; };
in
{
  users.users.scetrov = {
    packages = with pkgs; [
      insomnia
      jetbrains.rider
      unstable.brave
      unstable.framesh
      unstable.ghostty
      unstable.obsidian
      vscode-fhs
      yubioath-flutter
      unstable.keepassxs
    ];
  };
}
