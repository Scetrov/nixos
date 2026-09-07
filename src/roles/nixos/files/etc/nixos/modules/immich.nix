{ ... }:

let
  # NixOS 26.05's Immich 2.7.5 is blocked as insecure. Use the existing
  # nixos-unstable channel for the supported 3.x release until 26.05 is
  # refreshed; the NixOS service module remains package-compatible.
  unstable = import <nixos-unstable> { };
in
{
  services.immich = {
    enable = true;
    package = unstable.immich;
    port = 3000;
    host = "immich.net.scetrov.live";
    openFirewall = true;
  };
}
