{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.scetrov.services.miniflux;
  databaseSecrets = [
    config.age.secrets.miniflux_db_password.file
    config.age.secrets.miniflux_database_url.file
  ];
  oidcSecrets = [
    config.age.secrets.miniflux_oidc_client_id.file
    config.age.secrets.miniflux_oidc_client_secret.file
  ];
in
{
  options.scetrov.services.miniflux = {
    enable = lib.mkEnableOption "private native Miniflux feed reader";
    subscriptions = {
      enable = lib.mkEnableOption "explicit, credential-backed subscription plan/apply";
      operator = lib.mkOption {
        type = lib.types.str;
        default = "scetrov";
        description = "Exact Miniflux username verified before subscription sync.";
      };
      toolFile = lib.mkOption {
        type = lib.types.path;
        default = ./miniflux-subscriptions.py;
        internal = true;
      };
      catalogueFile = lib.mkOption {
        type = lib.types.path;
        default = ./miniflux-feeds.json;
        internal = true;
      };
    };
  };

  config = lib.mkMerge [
    (lib.mkIf (cfg.enable && cfg.subscriptions.enable) {
      age.secrets.miniflux_subscription_api_token = {
        file = /root/secrets/miniflux_subscription_api_token.age;
        mode = "0400";
      };
      users.groups.miniflux-subscriptions = { };
      users.users.miniflux-subscriptions = {
        isSystemUser = true;
        group = "miniflux-subscriptions";
      };
      # Stable shared ownership and lock for both explicitly invoked services.
      systemd.tmpfiles.rules = [
        "d /run/miniflux-subscriptions 0700 miniflux-subscriptions miniflux-subscriptions -"
      ];
      systemd.services = lib.genAttrs [ "miniflux-subscriptions" "miniflux-subscriptions-plan" ] (
        name:
        let
          operation = if name == "miniflux-subscriptions" then "apply" else "plan";
        in
        {
          description = "Explicit Miniflux subscription ${operation}";
          after = [ "miniflux.service" ];
          requisite = [ "miniflux.service" ];
          # No wantedBy, restart triggers or timers; switches must not invoke sync.
          restartIfChanged = false;
          stopIfChanged = false;
          serviceConfig = {
            Type = "oneshot";
            User = "miniflux-subscriptions";
            Group = "miniflux-subscriptions";
            ExecStart = "${pkgs.python3}/bin/python3 -u ${cfg.subscriptions.toolFile} ${operation} --catalogue ${cfg.subscriptions.catalogueFile} --operator ${lib.escapeShellArg cfg.subscriptions.operator} --credential-file %d/api-token";
            LoadCredential = [ "api-token:${config.age.secrets.miniflux_subscription_api_token.path}" ];
            TimeoutStartSec = 2500;
            UMask = "0077";
            NoNewPrivileges = true;
            PrivateTmp = true;
            PrivateDevices = true;
            ProtectSystem = "strict";
            ProtectHome = true;
            ProtectKernelTunables = true;
            ProtectKernelModules = true;
            ProtectControlGroups = true;
            ProtectClock = true;
            RestrictSUIDSGID = true;
            LockPersonality = true;
            MemoryDenyWriteExecute = true;
            CapabilityBoundingSet = "";
            RestrictAddressFamilies = [ "AF_INET" ];
            IPAddressDeny = "any";
            IPAddressAllow = "127.0.0.1/32";
            ReadWritePaths = [ "/run/miniflux-subscriptions" ];
            StandardOutput = "journal";
            StandardError = "journal";
          };
        }
      );
    })
    (lib.mkIf config.services.grafana.enable {
      # Inherit existing Grafana notification policies; do not create a receiver
      # or mutate the shared routing tree. Explicit deletion prevents stale
      # alerts after disabling the service and restarting Grafana.
      services.grafana.provision.alerting.rules.settings = {
        apiVersion = 1;
        deleteRules = lib.optional (!cfg.enable) {
          orgId = 1;
          uid = "miniflux-unavailable";
        };
        groups = lib.optional cfg.enable {
          orgId = 1;
          name = "Miniflux availability";
          folder = "Operations / Services";
          interval = "60s";
          rules = [
            {
              uid = "miniflux-unavailable";
              title = "MinifluxServiceUnavailable";
              condition = "B";
              for = "5m";
              noDataState = "Alerting";
              execErrState = "Alerting";
              labels = {
                severity = "critical";
                service = "miniflux";
                host = "habiki";
              };
              annotations = {
                summary = "Miniflux private metrics endpoint has been unavailable for five minutes";
                description = "Check miniflux.service, miniflux-dbsetup.service and the shared PostgreSQL container. See docs/miniflux.md.";
              };
              data = [
                {
                  refId = "A";
                  datasourceUid = "mimir";
                  relativeTimeRange = {
                    from = 600;
                    to = 0;
                  };
                  model = {
                    refId = "A";
                    expr = ''up{job="miniflux",service="miniflux"} == bool 0 or absent(up{job="miniflux",service="miniflux"})'';
                    instant = true;
                    range = false;
                    intervalMs = 1000;
                    maxDataPoints = 43200;
                  };
                }
                {
                  refId = "B";
                  datasourceUid = "__expr__";
                  relativeTimeRange = {
                    from = 0;
                    to = 0;
                  };
                  model = {
                    refId = "B";
                    type = "math";
                    expression = "$A > 0";
                  };
                }
              ];
            }
          ];
        };
      };
    })
    (lib.mkIf cfg.enable {
      assertions = [
        {
          assertion = config.scetrov.services.authentik.enable;
          message = "Miniflux requires the existing Authentik PostgreSQL service.";
        }
        {
          assertion = lib.getVersion config.services.miniflux.package == "2.3.3";
          message = "Reverify Miniflux release age/security before changing the approved 2.3.3 package.";
        }
      ];

      age.secrets = {
        miniflux_db_password = {
          file = /root/secrets/miniflux_db_password.age;
          mode = "0400";
        };
        miniflux_database_url = {
          file = /root/secrets/miniflux_database_url.age;
          mode = "0400";
        };
        miniflux_oidc_client_id = {
          file = /root/secrets/miniflux_oidc_client_id.age;
          mode = "0400";
        };
        miniflux_oidc_client_secret = {
          file = /root/secrets/miniflux_oidc_client_secret.age;
          mode = "0400";
        };
      };

      services.miniflux = {
        enable = true;
        createDatabaseLocally = false;
        config = {
          LISTEN_ADDR = "127.0.0.1:8091";
          BASE_URL = "https://feed.net.scetrov.live";
          DATABASE_URL = null;
          DATABASE_URL_FILE = "/run/credentials/miniflux.service/database-url";
          DATABASE_MAX_CONNS = 5;
          DATABASE_MIN_CONNS = 1;
          RUN_MIGRATIONS = 1;
          CREATE_ADMIN = 0;
          OAUTH2_PROVIDER = "oidc";
          OAUTH2_CLIENT_ID_FILE = "/run/credentials/miniflux.service/oidc-client-id";
          OAUTH2_CLIENT_SECRET_FILE = "/run/credentials/miniflux.service/oidc-client-secret";
          OAUTH2_OIDC_DISCOVERY_ENDPOINT = "https://identity.net.scetrov.live/application/o/miniflux/";
          OAUTH2_REDIRECT_URL = "https://feed.net.scetrov.live/oauth2/oidc/callback";
          OAUTH2_USER_CREATION = 1;
          DISABLE_LOCAL_AUTH = 1;
          METRICS_COLLECTOR = 1;
          METRICS_ALLOWED_NETWORKS = "127.0.0.1/32";
          LOG_LEVEL = "warning";
        };
      };

      # Native API authentication stays in Miniflux; never put forward_auth here.
      # Own this virtual host here rather than behind caddy.nix's Grafana guard.
      services.caddy = {
        enable = true;
        virtualHosts."feed.net.scetrov.live" = {
          useACMEHost = "scetrov.live";
          extraConfig = ''
            encode zstd gzip
            handle /metrics* {
              respond 404
            }
            handle {
              reverse_proxy 127.0.0.1:8091
            }
          '';
        };
      };

      services.prometheus.scrapeConfigs = lib.mkIf config.services.prometheus.enable [
        {
          job_name = "miniflux";
          scrape_interval = "60s";
          metrics_path = "/metrics";
          static_configs = [
            {
              targets = [ "127.0.0.1:8091" ];
              labels.service = "miniflux";
            }
          ];
        }
      ];

      systemd.services.miniflux-dbsetup = {
        description = "Reconcile the dedicated Miniflux PostgreSQL database";
        # Wants (not Requires/BindsTo) avoids stopping this completed setup and
        # the reader when the database container later restarts. Miniflux retries.
        wants = [ "podman-authentik-postgresql.service" ];
        after = [ "podman-authentik-postgresql.service" ];
        before = [ "miniflux.service" ];
        restartTriggers = databaseSecrets;
        path = [ pkgs.podman ];
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
          TimeoutStartSec = 240;
          UMask = "0077";
          LoadCredential = [ "db-password:${config.age.secrets.miniflux_db_password.path}" ];
          ExecStart = "${pkgs.python3}/bin/python3 ${./miniflux-dbsetup.py}";
        };
      };

      systemd.services.miniflux = {
        requires = [ "miniflux-dbsetup.service" ];
        after = [ "miniflux-dbsetup.service" ];
        partOf = [ "miniflux-dbsetup.service" ];
        restartTriggers = databaseSecrets ++ oidcSecrets;
        serviceConfig.LoadCredential = [
          "database-url:${config.age.secrets.miniflux_database_url.path}"
          "oidc-client-id:${config.age.secrets.miniflux_oidc_client_id.path}"
          "oidc-client-secret:${config.age.secrets.miniflux_oidc_client_secret.path}"
        ];
      };
    })
  ];
}
