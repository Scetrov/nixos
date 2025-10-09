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
      charles
      discord
      jetbrains.rider
      nerd-fonts.fira-code
      unstable.brave
      unstable.dotnet-ef
      unstable.framesh
      unstable.insomnia
      unstable.keepassxc
      unstable.obsidian
      unstable.sqlitestudio
      unstable.syncthingtray
      unstable.vscode-fhs
    ];
  };
}
