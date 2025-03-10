{ config, ... }:

{
  imports = [
    ./modules/acme.nix
    ./modules/dnscrypt-proxy.nix
    ./modules/traefik.nix
  ];
}