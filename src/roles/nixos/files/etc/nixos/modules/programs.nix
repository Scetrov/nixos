{ config, pkgs, ... }:

{
  programs.nix-ld.enable = true;

  programs.zsh.enable = true;

  users.defaultUserShell = pkgs.zsh;
  
  programs.neovim = {
    enable = true;
    defaultEditor = true;
  };

  programs.firefox.enable = true;

  programs.gnupg.agent = {
    enable = true;
    enableSSHSupport = true;
  };
}