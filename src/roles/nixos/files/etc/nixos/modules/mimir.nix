{ ... }:

{
  services.mimir = {
    enable = true;
    configuration = {
      memberlist.bind_port = 7947;
      multitenancy_enabled = false;
      usage_stats.enabled = false;
      server = {
        grpc_listen_port = 9097;
        http_listen_address = "127.0.0.1";
        http_listen_port = 8080;
      };
      ingester.ring.replication_factor = 1;
    };
  };
}