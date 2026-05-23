{ config, pkgs, ... }:

{
  imports = [
    ./modules/acme.nix
    ./modules/authentik.nix
    ./modules/blocky.nix
    ./modules/caddy.nix
    ./modules/dependency-track.nix
    ./modules/frontier-indexer.nix
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
    ./modules/grafana-mcp.nix
    ./modules/home-assistant.nix
  ];

  services.hermes-webui = {
    enable = true;
    enableCaddy = false;
    caddyListenAddress = "127.0.0.1";
    environmentFile = config.age.secrets.hermes_webui_env.path;
    extraEnvironment = {
      HERMES_WEBUI_TRUSTED_PROXY_AUTH_HEADER = "X-Authentik-Username";
      HERMES_WEBUI_TRUSTED_PROXY_NETS = "127.0.0.0/8, 10.0.0.0/8";
      # Setting this to empty string in 'environment' overrides any value in 'environmentFile'
      # and enables trusted proxy authentication in Hermes WebUI.
      HERMES_WEBUI_PASSWORD = "";
    };
  };

  age.secrets.hermes_webui_env = {
    file = /root/secrets/hermes_webui_env.age;
    owner = "hermes-webui";
  };

  scetrov.services.authentik.enable = true;
  scetrov.services.dependency-track.enable = true;
  scetrov.services.home-assistant = {
    enable = true;
    matter.enable = true;
  };
  scetrov.services.frontier-indexer = {
    enable = true;
    firstCheckpoint = "302790346";
  };
  services.grafana-mcp = {
    enable = true;
  };

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
