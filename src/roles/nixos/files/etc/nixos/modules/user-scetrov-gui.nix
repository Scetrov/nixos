{ config, pkgs, ... }:
let
  baseconfig = {
    allowUnfree = true;
  };
  unstable = import <nixos-unstable> { config = baseconfig; };

  vscode-fhs-devcontainers = pkgs.buildFHSEnv {
    name = "vscode-fhs-devcontainers";
    targetPkgs =
      p: with p; [
        unstable.vscode
        podman # podman CLI
        git
        gnupg
        cacert
        bashInteractive
      ];
    runScript = "bash";
    # expose both /var/run and /run/user for rootless sockets + your home
    extraMounts = [
      {
        source = "/var/run";
        target = "/var/run";
      }
      {
        source = "/run/user";
        target = "/run/user";
      }
      {
        source = "/home/scetrov";
        target = "/home/scetrov";
      }
    ];
  };

in
{
  virtualisation.podman = {
    enable = true;
    dockerCompat = true; # VS Code Dev Containers talks to "docker" API
  };

  # Required for rootless mappings
  users.users.scetrov.subUidRanges = [
    {
      startUid = 100000;
      count = 65536;
    }
  ];
  users.users.scetrov.subGidRanges = [
    {
      startGid = 100000;
      count = 65536;
    }
  ];

  users.users.scetrov = {
    packages = with pkgs; [
      charles
      discord
      jetbrains.rider
      nerd-fonts.fira-code
      sqlite
      unstable.antigravity
      unstable.brave
      unstable.claude-code
      unstable.code-cursor
      unstable.codex
      unstable.cursor-cli
      unstable.dotnet-ef
      unstable.framesh
      unstable.insomnia
      unstable.keepassxc
      unstable.obsidian
      unstable.sqlitestudio
      unstable.syncthingtray
      unstable.vscode
      vscode-fhs-devcontainers
    ];
  };

  environment.systemPackages = [ vscode-fhs-devcontainers ];
  environment.etc."profile.d/code-fhs.sh".text = ''
    code-fhs() {
      exec ${vscode-fhs-devcontainers}/bin/vscode-fhs-devcontainers -c "exec code ''${*:-.}"
    }
    export -f code-fhs
  '';
}
