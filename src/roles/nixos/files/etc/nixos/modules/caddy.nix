{ config, lib, ... }:

lib.mkIf config.services.grafana.enable {
  networking.firewall.allowedTCPPorts = [ 80 443 ];

  services.caddy = {
    enable = true;
    virtualHosts."metrics.net.scetrov.live" = {
      useACMEHost = "scetrov.live";
      extraConfig = ''
        encode zstd gzip

        header {
          Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
          X-Content-Type-Options nosniff
          X-Frame-Options SAMEORIGIN
          Referrer-Policy no-referrer-when-downgrade
        }

        handle /loki* {
          reverse_proxy 127.0.0.1:3100
        }

        handle_path /tempo* {
          reverse_proxy 127.0.0.1:3200
        }

        handle_path /otlp* {
          reverse_proxy 127.0.0.1:4318
        }

        handle_path /mimir* {
          reverse_proxy 127.0.0.1:8080
        }

        handle /prometheus* {
          reverse_proxy 127.0.0.1:9090
        }

        handle /pyroscope* {
          reverse_proxy 127.0.0.1:4040
        }

        handle_path /alloy* {
          reverse_proxy 127.0.0.1:12345
        }

        handle /oncall* {
          reverse_proxy 127.0.0.1:18080
        }

        handle /grafana* {
          reverse_proxy 127.0.0.1:3000
        }

        redir / /grafana
      '';
    };
  };
}