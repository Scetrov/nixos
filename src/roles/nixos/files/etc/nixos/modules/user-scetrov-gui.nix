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
      unstable.jetbrains.rider
      unstable.brave
      unstable.framesh
      unstable.ghostty
      unstable.obsidian
      unstable.dotnet-ef
      vscode-fhs
      yubioath-flutter
      unstable.keepassxc
      unstable.sqlitestudio
    ];
  };
}
