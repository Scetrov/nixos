{ config, ... }:

{
  imports = [
    ./modules/acme.nix
    ./modules/traefik.nix
    ./modules/prometheus.nix
    ./modules/grafana.nix
    ./modules/ethereum-erigon-sepolia.nix
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
    ];
  };
}