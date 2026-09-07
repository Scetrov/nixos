{ pkgs, ... }:

{
  services.prometheus.exporters.blackbox = {
    enable = true;
    configFile = pkgs.writeText "headscale-blackbox.yml" ''
      modules:
        headscale_https:
          prober: http
          timeout: 10s
          http:
            fail_if_not_ssl: true
            valid_status_codes: [200]
            tls_config:
              server_name: headscale.net.scetrov.live
            headers:
              Host: headscale.net.scetrov.live
    '';
  };

  services.prometheus = {
    enable = true;
    listenAddress = "127.0.0.1";
    port = 9090;
    retentionTime = "15d";
    webExternalUrl = "https://metrics.net.scetrov.live";
    extraFlags = [ "--web.route-prefix=/" ];
    globalConfig = {
      external_labels = {
        cluster = "net";
        host = "habiki";
      };
      scrape_interval = "15s";
    };
    remoteWrite = [
      {
        url = "http://127.0.0.1:8080/api/v1/push";
      }
    ];
    rules = [
      ''
        groups:
          - name: headscale
            rules:
              - alert: HeadscaleServiceUnavailable
                expr: up{job="headscale"} != 1
                for: 5m
                labels:
                  severity: critical
                annotations:
                  summary: Headscale local metrics endpoint is unavailable
              - alert: HeadscaleEdgeUnavailable
                expr: probe_success{job="headscale-edge"} != 1
                for: 5m
                labels:
                  severity: critical
                annotations:
                  summary: Headscale local HTTPS edge is unavailable
          - name: garage
            rules:
              - alert: GarageServiceUnavailable
                expr: up{job="garage"} != 1
                for: 5m
                labels:
                  severity: critical
                annotations:
                  summary: Garage metrics endpoint is unavailable
              - alert: GarageStorageReserveLow
                expr: node_filesystem_avail_bytes{host="habiki",mountpoint="/",fstype!~"tmpfs|fuse.lxcfs|overlay|squashfs"} < 536870912000
                for: 15m
                labels:
                  severity: warning
                annotations:
                  summary: Garage host storage has less than the 500 GiB reserve
                  description: Free space on Habiki's persistent Garage filesystem is below the required recovery reserve.
      ''
    ];
    scrapeConfigs = [
      {
        job_name = "prometheus";
        static_configs = [
          {
            targets = [ "127.0.0.1:9090" ];
          }
        ];
      }
      {
        job_name = "node";
        static_configs = [
          {
            targets = [ "127.0.0.1:9100" ];
          }
        ];
      }
      {
        job_name = "blocky";
        static_configs = [
          {
            targets = [ "127.0.0.1:4000" ];
          }
        ];
      }
      {
        job_name = "grafana";
        static_configs = [
          {
            targets = [ "127.0.0.1:3005" ];
          }
        ];
      }
      {
        job_name = "loki";
        static_configs = [
          {
            targets = [ "127.0.0.1:3100" ];
          }
        ];
      }
      {
        job_name = "tempo";
        static_configs = [
          {
            targets = [ "127.0.0.1:3200" ];
          }
        ];
      }
      {
        job_name = "mimir";
        static_configs = [
          {
            targets = [ "127.0.0.1:8080" ];
          }
        ];
      }
      {
        job_name = "pyroscope";
        static_configs = [
          {
            targets = [ "127.0.0.1:4040" ];
          }
        ];
      }
      {
        job_name = "alloy";
        static_configs = [
          {
            targets = [ "127.0.0.1:12345" ];
          }
        ];
      }
      {
        job_name = "garage";
        metrics_path = "/metrics";
        bearer_token_file = "/run/agenix/garage_metrics_token";
        static_configs = [
          {
            targets = [ "127.0.0.1:3903" ];
            labels.service = "garage";
          }
        ];
      }
      {
        job_name = "headscale";
        static_configs = [
          {
            targets = [ "127.0.0.1:9091" ];
            labels.service = "headscale";
          }
        ];
      }
      {
        job_name = "headscale-edge";
        metrics_path = "/probe";
        params.module = [ "headscale_https" ];
        static_configs = [
          {
            targets = [ "https://127.0.0.1:8443/health" ];
          }
        ];
        relabel_configs = [
          {
            source_labels = [ "__address__" ];
            target_label = "__param_target";
          }
          {
            source_labels = [ "__param_target" ];
            target_label = "instance";
          }
          {
            target_label = "__address__";
            replacement = "127.0.0.1:9115";
          }
        ];
      }
      {
        job_name = "github-repository-observability";
        scrape_interval = "60s";
        static_configs = [
          {
            targets = [ "127.0.0.1:9177" ];
            labels = {
              service = "github-repository-observability";
            };
          }
        ];
      }
    ];
  };
}
