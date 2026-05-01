{ pkgs, ... }:

{
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
        root_url = "https://metrics.net.scetrov.live/";
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
}