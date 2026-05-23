{ config, lib, ... }:

let
  cfg = config.scetrov.services.home-assistant;
in
{
  options.scetrov.services.home-assistant = {
    enable = lib.mkEnableOption "Home Assistant service";
  };

  config = lib.mkIf cfg.enable {
    # Operator Reminder:
    # After deployment, you must manually add the following configuration to
    # /var/lib/homeassistant/configuration.yaml for the Caddy reverse proxy to work correctly:
    #
    # http:
    #   use_x_forwarded_for: true
    #   trusted_proxies:
    #     - 127.0.0.1
    #     - 10.229.0.0/16

    virtualisation.oci-containers.containers.homeassistant = {
      image = "ghcr.io/home-assistant/home-assistant:stable";
      autoStart = true;
      environment = {
        TZ = "Europe/London";
      };
      volumes = [
        "/var/lib/homeassistant:/config"
      ];
      extraOptions = [
        "--network=host"
      ];
    };

    systemd.tmpfiles.rules = [
      "d /var/lib/homeassistant 0750 root root -"
    ];

    networking.firewall.allowedUDPPorts = [
      1900 # SSDP / UPnP discovery
      5353 # mDNS discovery
    ];
  };
}
