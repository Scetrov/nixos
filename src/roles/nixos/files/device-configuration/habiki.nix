{ config, pkgs, ... }:

{
  imports = [
    ./modules/acme.nix
    ./modules/authentik.nix
    ./modules/alloy.nix
    ./modules/blocky.nix
    ./modules/caddy.nix
    ./modules/grafana.nix
    ./modules/immich.nix
    ./modules/k6.nix
    ./modules/local-networking.nix
    ./modules/loki.nix
    ./modules/mimir.nix
    ./modules/oncall.nix
    ./modules/pyroscope.nix
    ./modules/prometheus.nix
    ./modules/tempo.nix
    ./modules/hermes.nix
    ./modules/user-scetrov-filebrowser.nix
    ./modules/user-scetrov-syncthing.nix
  ];

  services.hermes-webui = {
    enable = true;
    caddyListenAddress = "0.0.0.0";
    environmentFile = config.age.secrets.hermes_webui_env.path;
  };

  age.secrets.hermes_webui_env = {
    file = /root/secrets/hermes_webui_env.age;
    owner = "hermes-webui";
  };

  scetrov.services.authentik.enable = true;
  
  blocky.bindAddr = "10.229.53.2:53";

  networking = {
    wireless.enable = false;
    networkmanager = {
      enable = true;
      plugins = [ pkgs.networkmanager-openvpn ];
    };
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
