{ config, ... }:

{
  imports = [
    ./modules/acme.nix
    ./modules/blocky.nix
    ./modules/grafana.nix
    ./modules/immich.nix
    ./modules/local-networking.nix
    ./modules/prometheus.nix
    ./modules/traefik.nix
    ./modules/user-scetrov-filebrowser.nix
    ./modules/user-scetrov-syncthing.nix
  ];

  networking = {
    wireless.enable = false;
    networkmanager.enable = true;
    hostName = "habiki";
    defaultGateway = "10.229.0.1";
    interfaces.eth0.ipv4.addresses = [
      {
        address = "10.229.10.2";
        prefixLength = 16;
      }
      {
        address = "10.229.53.2";
        prefixLength = 16;
      }
    ];
  };
}
