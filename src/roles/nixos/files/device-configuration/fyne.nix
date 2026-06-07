{ config, pkgs, ... }:

{
  imports = [
    "${fetchTarball "https://github.com/NixOS/nixos-hardware/tarball/master"}/raspberry-pi/4"
    ./modules/blocky.nix
    ./modules/bootstrap-dns.nix
    ./modules/local-networking.nix
    ./modules/user-scetrov-syncthing.nix
  ];

  # nixos-hardware/master currently builds the Pi kernel via structuredExtraConfig,
  # which can drift out of sync with the host's nixpkgs kernel builder.
  boot.kernelPackages = pkgs.linuxPackages_rpi4;

  blocky.bindAddr = "10.229.53.1:53";

  networking = {
    networkmanager = {
      enable = true;
      plugins = [ pkgs.networkmanager-openvpn ];
    };
    hostName = "fyne";
    defaultGateway = "10.229.0.1";
    interfaces.eth0.ipv4.addresses = [
      {
        address = "10.229.10.1";
        prefixLength = 16;
      }
      {
        address = "10.229.53.1";
        prefixLength = 16;
      }
    ];
  };
}
