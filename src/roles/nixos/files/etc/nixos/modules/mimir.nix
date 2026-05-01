{ ... }:

{
  services.mimir = {
    enable = true;
    configuration = {
      multitenancy_enabled = false;
      usage_stats.enabled = false;
      server = {
        http_listen_address = "127.0.0.1";
        http_listen_port = 8080;
      };
      ingester.ring.replication_factor = 1;
    };
  };
}