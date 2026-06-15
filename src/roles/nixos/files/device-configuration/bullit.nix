{ config, pkgs, ... }:

{
  imports = [
    ./modules/home-wifi.nix
    ./modules/local-networking.nix
    ./modules/sunshine.nix
    ./modules/user-scetrov-gui.nix
    ./modules/user-scetrov-syncthing.nix
    ./modules/xrdp.nix
  ];

  networking = {
    networkmanager = {
      enable = true;
      plugins = [ pkgs.networkmanager-openvpn ];
    };
    hostName = "bullit";
    defaultGateway = "10.229.0.1";
    interfaces.eth0.ipv4.addresses = [
      {
        address = "10.229.10.10";
        prefixLength = 16;
      }
    ];
  };
}
