{ config, ... }:

{
  imports = [
    ./modules/acme.nix
    ./modules/traefik.nix
  ];
}