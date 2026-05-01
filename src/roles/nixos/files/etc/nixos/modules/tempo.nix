{ ... }:

{
  services.tempo = {
    enable = true;
    settings = {
      multitenancy_enabled = false;
      server = {
        http_listen_address = "127.0.0.1";
        http_listen_port = 3200;
      };
      distributor.receivers.otlp.protocols = {
        grpc.endpoint = "127.0.0.1:4317";
        http.endpoint = "127.0.0.1:4318";
      };
      ingester = {
        max_block_bytes = 104857600;
        max_block_duration = "5m";
      };
      compactor.compaction = {
        block_retention = "168h";
        compacted_block_retention = "1h";
      };
      metrics_generator = {
        registry.external_labels = {
          cluster = "net";
          host = "habiki";
        };
        storage.path = "/var/lib/tempo/generator/wal";
      };
      overrides.defaults.metrics_generator.processors = [
        "service-graphs"
        "span-metrics"
      ];
      storage.trace = {
        backend = "local";
        local.path = "/var/lib/tempo/blocks";
        wal.path = "/var/lib/tempo/wal";
      };
      usage_report.reporting_enabled = false;
    };
  };
}