{ pkgs, ... }:

let
  settingsFile = pkgs.formats.yaml { }.generate "pyroscope.yaml" {
    target = "all";
    multitenancy_enabled = false;
    analytics.reporting_enabled = false;
    api."base-url" = "https://metrics.net.scetrov.live/pyroscope";
    server = {
      http_listen_address = "127.0.0.1";
      http_listen_port = 4040;
      http_path_prefix = "/pyroscope";
      grpc_listen_address = "127.0.0.1";
      grpc_listen_port = 4041;
    };
    storage = {
      backend = "filesystem";
      filesystem.dir = "/var/lib/pyroscope/store";
    };
    pyroscopedb.data_path = "/var/lib/pyroscope/data";
  };
in
{
  environment.systemPackages = [ pkgs.pyroscope ];

  systemd.services.pyroscope = {
    description = "Grafana Pyroscope";
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];
    wantedBy = [ "multi-user.target" ];
    serviceConfig = {
      DynamicUser = true;
      ExecStart = "${pkgs.pyroscope}/bin/pyroscope -config.file=${settingsFile}";
      NoNewPrivileges = true;
      ProtectSystem = "strict";
      Restart = "always";
      StateDirectory = "pyroscope";
      WorkingDirectory = "/var/lib/pyroscope";
    };
  };
}