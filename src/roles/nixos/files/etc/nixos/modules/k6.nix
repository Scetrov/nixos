{ pkgs, ... }:

{
  environment.systemPackages = with pkgs; [
    har-to-k6
    k6
    xk6
  ];
}