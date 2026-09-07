{
  config,
  lib,
  pkgs,
  ...
}:

let
  dataDir = "/var/lib/garage/data";
  metadataDir = "/var/lib/garage/meta";
in
{
  # Rendered by the encrypted agenix workflow. Garage reads this as an
  # EnvironmentFile, so the RPC secret never enters the generated TOML.
  age.secrets = {
    garage_rpc_secret = {
      file = /root/secrets/garage_rpc_secret.age;
      owner = "root";
      group = "root";
      mode = "0400";
    };
    garage_admin_environment = {
      file = /root/secrets/garage_admin_environment.age;
      owner = "root";
      group = "root";
      mode = "0400";
    };
    garage_metrics_token = {
      file = /root/secrets/garage_metrics_token.age;
      owner = "root";
      group = "prometheus";
      mode = "0440";
    };
    garage_metrics_environment = {
      file = /root/secrets/garage_metrics_environment.age;
      owner = "root";
      group = "root";
      mode = "0400";
    };
    garage_reapers_arsenal_s3_credentials = {
      file = /root/secrets/garage_reapers_arsenal_s3_credentials.age;
      owner = "root";
      group = "root";
      mode = "0400";
    };
  };

  services.garage = {
    enable = true;
    package = pkgs.garage;
    environmentFile = config.age.secrets.garage_rpc_secret.path;
    settings = {
      replication_factor = 1;
      metadata_dir = metadataDir;
      data_dir = dataDir;
      metadata_fsync = true;
      data_fsync = true;

      # Keep all endpoints private until the Headscale address, DNS, TLS, and
      # firewall policy are configured in the following tasks.
      rpc_bind_addr = "127.0.0.1:3901";
      rpc_public_addr = "127.0.0.1:3901";
      s3_api = {
        api_bind_addr = "127.0.0.1:3900";
        s3_region = "garage";
      };
      admin.api_bind_addr = "127.0.0.1:3903";
      admin.metrics_require_token = true;
    };
  };

  systemd.services.garage.serviceConfig = {
    StateDirectoryMode = "0750";
    UMask = "0077";
    # Systemd reads the root-only agenix files before dropping privileges and
    # passes their variables to Garage. The dynamic Garage identity never needs
    # direct read access to token files.
    EnvironmentFile = lib.mkAfter [
      config.age.secrets.garage_admin_environment.path
      config.age.secrets.garage_metrics_environment.path
    ];
  };
}
