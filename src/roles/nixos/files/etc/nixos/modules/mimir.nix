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
        http_listen_address = "0.0.0.0";
        http_listen_port = 8080;
      };
      ingester.ring.replication_factor = 1;
    };
  };

  networking.firewall.extraCommands = ''
    iptables -A nixos-fw -p tcp -s 10.229.10.1 --dport 8080 -j nixos-fw-accept
    iptables -A nixos-fw -p tcp -s 10.229.10.10 --dport 8080 -j nixos-fw-accept
  '';
}
