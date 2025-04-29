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
      fira-code-nerdfont
      unstable.insomnia
      unstable.brave
      unstable.dotnet-ef
      unstable.framesh
      unstable.jetbrains.rider
      unstable.keepassxc
      unstable.obsidian
      unstable.sqlitestudio
      unstable.syncthingtray
      unstable.vscode-fhs
      yubioath-flutter
    ];
  };
}
