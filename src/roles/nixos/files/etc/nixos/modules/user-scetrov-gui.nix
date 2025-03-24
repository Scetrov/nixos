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
      discord
      fira-code-nerdfont
      insomnia
      charles
      unstable.brave
      unstable.dotnet-ef
      unstable.framesh
      unstable.jetbrains.rider
      unstable.keepassxc
      unstable.obsidian
      unstable.sqlitestudio
      unstable.vscode-fhs
      yubioath-flutter
    ];
  };
}
