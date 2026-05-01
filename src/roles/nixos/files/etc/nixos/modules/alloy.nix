{ ... }:

{
  environment.etc."alloy/config.alloy".text = ''
    loki.write "local" {
      endpoint {
        url = "http://127.0.0.1:3100/loki/api/v1/push"
      }
    }

    loki.source.journal "systemd" {
      forward_to = [loki.write.local.receiver]
      labels = {
        host = "habiki",
        job  = "systemd-journal",
      }
    }

    local.file_match "varlogs" {
      path_targets = [{
        __path__ = "/var/log/*.log",
        host     = "habiki",
        job      = "varlogs",
      }]
    }

    loki.source.file "varlogs" {
      targets    = local.file_match.varlogs.targets
      forward_to = [loki.write.local.receiver]
    }

    otelcol.receiver.otlp "ingest" {
      grpc {
        endpoint = "127.0.0.1:4317"
      }

      http {
        endpoint = "127.0.0.1:4318"
      }

      output {
        traces = [otelcol.exporter.otlphttp.tempo.input]
      }
    }

    otelcol.exporter.otlphttp "tempo" {
      client {
        endpoint = "http://127.0.0.1:4318"

        tls {
          insecure             = true
          insecure_skip_verify = true
        }
      }
    }
  '';

  services.alloy = {
    enable = true;
    extraFlags = [
      "--disable-reporting"
      "--server.http.listen-addr=127.0.0.1:12345"
      "--storage.path=/var/lib/alloy/data"
    ];
  };

  systemd.services.alloy.serviceConfig.SupplementaryGroups = [
    "adm"
    "systemd-journal"
  ];
}