{ config, lib, ... }:

lib.mkIf config.services.grafana.enable {
  networking.firewall.allowedTCPPorts = [
    80
    443
    8443
  ];

  age.secrets.loki_token_hash = {
    file = /root/secrets/loki_token_hash.age;
    owner = "caddy";
  };
  age.secrets.mcp_client_token = {
    file = /root/secrets/mcp_client_token.age;
    owner = "caddy";
  };

  systemd.services.caddy.serviceConfig.EnvironmentFile = [
    "/run/agenix/loki_token_hash"
    "/run/agenix/mcp_client_token"
  ];

  services.caddy = {
    enable = true;
    virtualHosts."metrics.net.scetrov.live" = {
      useACMEHost = "scetrov.live";
      extraConfig = ''
        encode zstd gzip

        @auth_routes {
          path /loki* /tempo* /otlp* /mimir* /prometheus* /pyroscope* /alloy* /frontier-indexer* /oncall*
          not path /loki/api/v1/push
        }
        forward_auth @auth_routes http://127.0.0.1:9000 {
          uri /outpost.goauthentik.io/auth/caddy
          copy_headers X-Authentik-Username X-Authentik-Groups X-Authentik-Email X-Authentik-Name X-Authentik-Uid
        }

        # Tile URLs live under /grafana so the browser sends the Grafana
        # session cookie (scoped to that subpath). Check Grafana's org API,
        # which accepts both human sessions and renderer service accounts;
        # /api/user returns 404 for the renderer's service-account identity.
        @project_zomboid_map path /grafana/project-zomboid-map/*
        forward_auth @project_zomboid_map http://127.0.0.1:3005 {
          uri /grafana/api/org
        }

        header {
          Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
          X-Content-Type-Options nosniff
          X-Frame-Options SAMEORIGIN
          Referrer-Policy no-referrer-when-downgrade
        }

        handle /loki/api/v1/push {
          basic_auth {
            log-pusher {$LOKI_TOKEN_HASH}
          }
          reverse_proxy 127.0.0.1:3100
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

        handle_path /prometheus* {
          reverse_proxy 127.0.0.1:9090
        }

        handle /pyroscope* {
          reverse_proxy 127.0.0.1:4040
        }

        handle_path /alloy* {
          reverse_proxy 127.0.0.1:12345
        }

        handle_path /frontier-indexer/metrics* {
          reverse_proxy 127.0.0.1:9184
        }

        handle /oncall* {
          reverse_proxy 127.0.0.1:18080
        }

        handle /mcp* {
          @mcp_auth {
            not header Authorization "Bearer {$MCP_CLIENT_TOKEN}"
          }
          respond @mcp_auth "Unauthorized" 401

          reverse_proxy 127.0.0.1:8000
        }

        handle_path /grafana/project-zomboid-map/* {
          root * /var/lib/project-zomboid-map/tiles
          file_server
        }

        handle /grafana* {
          reverse_proxy 127.0.0.1:3005
        }

        redir / /grafana
      '';
    };

    virtualHosts."hermes.net.scetrov.live" = lib.mkIf config.services.hermes-webui.enable {
      useACMEHost = "scetrov.live";
      extraConfig = ''
        forward_auth http://127.0.0.1:9000 {
          uri /outpost.goauthentik.io/auth/caddy
          copy_headers X-Authentik-Username X-Authentik-Groups X-Authentik-Email X-Authentik-Name X-Authentik-Uid
        }
        encode zstd gzip
        reverse_proxy 127.0.0.1:8787
      '';
    };

    virtualHosts."homeassistant.net.scetrov.live" =
      lib.mkIf config.scetrov.services.home-assistant.enable
        {
          useACMEHost = "scetrov.live";
          extraConfig = ''
            encode zstd gzip
            reverse_proxy 127.0.0.1:8123
          '';
        };

    # Keep this site on Caddy's shared HTTPS listener so Caddy can start before
    # tailscaled has assigned Habiki's tailnet address. Restrict access by the
    # peer source address instead of binding to an address that may not exist.
    virtualHosts."s3.tailnet.net.scetrov.live" = {
      useACMEHost = "s3.tailnet.net.scetrov.live";
      extraConfig = ''
        @notTailnet not remote_ip 100.64.0.0/10
        respond @notTailnet "Forbidden" 403

        encode zstd gzip
        reverse_proxy 127.0.0.1:3900
      '';
    };

    # This site deliberately has no forward_auth directive: Headscale clients
    # authenticate through their enrolment key and controller policy instead.
    virtualHosts."headscale.net.scetrov.live:8443" = {
      useACMEHost = "scetrov.live";
      extraConfig = ''
        encode zstd gzip
        reverse_proxy 127.0.0.1:8090
      '';
    };
  };
}
