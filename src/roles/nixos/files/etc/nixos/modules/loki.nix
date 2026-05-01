{ ... }:

{
  services.loki = {
    enable = true;
    configuration = {
      analytics.reporting_enabled = false;
      auth_enabled = false;
      common = {
        instance_addr = "127.0.0.1";
        path_prefix = "/var/lib/loki";
        replication_factor = 1;
        ring.kvstore.store = "inmemory";
      };
      compactor = {
        retention_enabled = true;
        working_directory = "/var/lib/loki/compactor";
      };
      limits_config = {
        reject_old_samples = true;
        reject_old_samples_max_age = "168h";
        retention_period = "168h";
      };
      ruler.storage = {
        local.directory = "/var/lib/loki/rules";
        type = "local";
      };
      schema_config.configs = [
        {
          from = "2024-01-01";
          index = {
            period = "24h";
            prefix = "index_";
          };
          object_store = "filesystem";
          schema = "v13";
          store = "tsdb";
        }
      ];
      server = {
        grpc_listen_address = "127.0.0.1";
        grpc_listen_port = 9096;
        http_listen_address = "127.0.0.1";
        http_listen_port = 3100;
      };
      storage_config = {
        filesystem.directory = "/var/lib/loki/chunks";
        tsdb_shipper = {
          active_index_directory = "/var/lib/loki/tsdb-index";
          cache_location = "/var/lib/loki/tsdb-cache";
        };
      };
    };
  };
}