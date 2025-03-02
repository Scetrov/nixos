{ config, pkgs, ... }:
let
  baseconfig = { allowUnfree = true; };
in {
  programs.zsh = {
    enable = true;
    autosuggestions.enable = true;
    syntaxHighlighting.enable = true;
  };
  
  users.defaultUserShell = pkgs.zsh;
}