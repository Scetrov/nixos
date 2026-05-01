{ ... }:

{
  services.prometheus = {
    enable = true;
    listenAddress = "127.0.0.1";
    port = 9090;
    retentionTime = "15d";
    webExternalUrl = "https://metrics.net.scetrov.live/prometheus";
    exporters.node = {
      enable = true;
      enabledCollectors = [ "systemd" ];
      listenAddress = "127.0.0.1";
      port = 9100;
    };
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
            targets = [ "127.0.0.1:3000" ];
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
    ];
  };
}