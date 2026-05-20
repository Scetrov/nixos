{ config, lib, ... }:

{
  users.users.alloy = {
    isSystemUser = true;
    group = "alloy";
    extraGroups = [ "adm" "systemd-journal" ];
  };
  users.groups.alloy = {};

  age.secrets.loki_token = {
    file = /root/secrets/loki_token.age;
    owner = "alloy";
  };

  environment.etc."alloy/config.alloy".text = ''
    loki.write "central" {
      endpoint {
        url = "https://metrics.net.scetrov.live/loki/api/v1/push"
        basic_auth {
          username = "log-pusher"
          password_file = "/run/agenix/loki_token"
        }
      }
    }

    loki.relabel "journal" {
      forward_to = []

      rule {
        source_labels = ["__journal__systemd_unit"]
        target_label  = "unit"
      }

      rule {
        source_labels = ["__journal_syslog_identifier"]
        target_label  = "syslog_identifier"
      }

      rule {
        source_labels = ["__journal_priority_keyword"]
        target_label  = "journal_priority"
      }
    }

    loki.source.journal "systemd" {
      forward_to    = [loki.write.central.receiver]
      relabel_rules = loki.relabel.journal.rules
      labels = {
        host = "${config.networking.hostName}",
        job  = "systemd-journal",
      }
    }

    local.file_match "varlogs" {
      path_targets = [{
        __path__ = "/var/log/*.log",
        host     = "${config.networking.hostName}",
        job      = "varlogs",
      }]
    }

    loki.source.file "varlogs" {
      targets    = local.file_match.varlogs.targets
      forward_to = [loki.write.central.receiver]
    }

    prometheus.exporter.unix "local" {
      include_exporter_metrics = true
    }

    prometheus.scrape "local" {
      targets    = prometheus.exporter.unix.local.targets
      forward_to = [prometheus.remote_write.central.receiver]

      job_name = "node"
      scrape_interval = "15s"

      clustering {
        enabled = false
      }
    }

    prometheus.remote_write "central" {
      endpoint {
        url = "http://10.229.10.2:8080/api/v1/push"
      }

      external_labels = {
        cluster = "net",
        host    = "${config.networking.hostName}",
      }
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

  systemd.tmpfiles.rules = [
    "d /var/lib/alloy 0750 alloy alloy -"
    "d /var/lib/alloy/data 0750 alloy alloy -"
    "Z /var/lib/alloy - alloy alloy -"
  ];

  systemd.services.alloy.serviceConfig = {
    DynamicUser = lib.mkForce false;
    User = "alloy";
    Group = "alloy";
  };
}
