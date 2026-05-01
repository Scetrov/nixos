{ config, lib, pkgs, ... }:

let
  cfg = config.scetrov.services.authentik;
  authentikEnvFile = pkgs.writeText "authentik.env" ''
    AUTHENTIK_SECRET_KEY=file://${config.age.secrets.authentik_secret_key.path}
    AUTHENTIK_LISTEN__HTTP=127.0.0.1:${toString cfg.port}
    AUTHENTIK_POSTGRESQL__HOST=/run/postgresql
    AUTHENTIK_POSTGRESQL__NAME=authentik
    AUTHENTIK_POSTGRESQL__USER=authentik
    AUTHENTIK_POSTGRESQL__PASSWORD=file://${config.age.secrets.authentik_postgresql_password.path}
    AUTHENTIK_POSTGRESQL__PORT=5432
  '';
in
{
  options.scetrov.services.authentik = {
    enable = lib.mkEnableOption "Authentik identity service";

    domain = lib.mkOption {
      type = lib.types.str;
      default = "identity.net.scetrov.live";
      description = "Public domain used for the Authentik web UI.";
    };

    port = lib.mkOption {
      type = lib.types.port;
      default = 9000;
      description = "Local Authentik HTTP port proxied by Caddy.";
    };
  };

  config = lib.mkIf cfg.enable {
    age.secrets.authentik_secret_key = {
      file = /root/secrets/authentik_secret_key.age;
      owner = "authentik";
      group = "authentik";
      mode = "0400";
    };

    age.secrets.authentik_postgresql_password = {
      file = /root/secrets/authentik_postgresql_password.age;
      owner = "authentik";
      group = "authentik";
      mode = "0400";
    };

    networking.firewall.allowedTCPPorts = [ 80 443 ];

    services.authentik = {
      enable = true;
      environmentFile = authentikEnvFile;
    };

    services.postgresql = {
      enable = true;
      ensureDatabases = [ "authentik" ];
      ensureUsers = [
        {
          name = "authentik";
          ensureDBOwnership = true;
        }
      ];
    };

    services.caddy = {
      enable = true;
      virtualHosts."${cfg.domain}" = {
        useACMEHost = "scetrov.live";
        extraConfig = ''
          encode zstd gzip
          reverse_proxy 127.0.0.1:${toString cfg.port}
        '';
      };
    };
  };
}