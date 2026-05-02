{ config, pkgs, ... }:

{
  age.secrets.grafana_authentik_client_id.file = /root/secrets/grafana_authentik_client_id.age;
  age.secrets.grafana_authentik_client_secret.file = /root/secrets/grafana_authentik_client_secret.age;

  services.grafana = {
    enable = true;
    declarativePlugins = with pkgs.grafanaPlugins; [
      grafana-lokiexplore-app
      grafana-oncall-app
      grafana-pyroscope-app
    ];
    settings = {
      analytics = {
        check_for_plugin_updates = false;
        reporting_enabled = false;
      };
      feature_toggles.enable = "externalServiceAccounts accessControlOnCall";
      log.mode = "console";
      metrics.enabled = true;
      security = {
        cookie_secure = true;
        disable_gravatar = true;
      };
      server = {
        domain = "metrics.net.scetrov.live";
        enable_gzip = true;
        http_addr = "127.0.0.1";
        http_port = 3000;
      };
      users = {
        allow_sign_up = false;
        default_theme = "system";
      };
    };
    provision = {
      datasources.settings = {
        apiVersion = 1;
        datasources = [
          {
            access = "proxy";
            editable = false;
            isDefault = true;
            name = "Mimir";
            type = "prometheus";
            uid = "mimir";
            url = "http://127.0.0.1:8080/prometheus";
          }
          {
            access = "proxy";
            editable = false;
            name = "Prometheus";
            type = "prometheus";
            uid = "prometheus";
            url = "http://127.0.0.1:9090";
          }
          {
            access = "proxy";
            editable = false;
            name = "Loki";
            type = "loki";
            uid = "loki";
            url = "http://127.0.0.1:3100";
          }
          {
            access = "proxy";
            editable = false;
            name = "Tempo";
            type = "tempo";
            uid = "tempo";
            url = "http://127.0.0.1:3200";
            jsonData = {
              nodeGraph.enabled = true;
              search.hide = false;
              serviceMap.datasourceUid = "mimir";
              tracesToLogs = {
                datasourceUid = "loki";
                mapTagNamesEnabled = true;
                spanEndTimeShift = "1m";
                spanStartTimeShift = "1m";
              };
              tracesToMetrics = {
                datasourceUid = "mimir";
                spanEndTimeShift = "1m";
                spanStartTimeShift = "1m";
              };
            };
          }
          {
            access = "proxy";
            editable = false;
            name = "Pyroscope";
            type = "grafana-pyroscope-datasource";
            uid = "pyroscope";
            url = "http://127.0.0.1:4040";
          }
        ];
      };
    };
  };

  systemd.services.grafana = {
    environment = {
      GF_AUTH_GENERIC_OAUTH_ENABLED = "true";
      GF_AUTH_GENERIC_OAUTH_NAME = "authentik";
      GF_AUTH_GENERIC_OAUTH_SCOPES = "openid profile email entitlements";
      GF_AUTH_GENERIC_OAUTH_AUTH_URL = "https://identity.net.scetrov.live/application/o/authorize/";
      GF_AUTH_GENERIC_OAUTH_TOKEN_URL = "https://identity.net.scetrov.live/application/o/token/";
      GF_AUTH_GENERIC_OAUTH_API_URL = "https://identity.net.scetrov.live/application/o/userinfo/";
      GF_AUTH_SIGNOUT_REDIRECT_URL = "https://identity.net.scetrov.live/application/o/grafana/end-session/";
      GF_AUTH_OAUTH_AUTO_LOGIN = "true";
      GF_AUTH_GENERIC_OAUTH_ROLE_ATTRIBUTE_PATH = "contains(entitlements[*], 'Grafana Admins') && 'Admin' || contains(entitlements[*], 'Grafana Editors') && 'Editor' || 'Viewer'";
      GF_SERVER_ROOT_URL = "https://metrics.net.scetrov.live/grafana";
      GF_SERVER_SERVE_FROM_SUB_PATH = "true";
    };
    serviceConfig.EnvironmentFile = [
      config.age.secrets.grafana_authentik_client_id.path
      config.age.secrets.grafana_authentik_client_secret.path
    ];
  };
}