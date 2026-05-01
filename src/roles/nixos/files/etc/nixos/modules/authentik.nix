{ config, lib, pkgs, ... }:

let
  cfg = config.scetrov.services.authentik;
  stateDir = "/var/lib/authentik";
  dataDir = "${stateDir}/data";
  templatesDir = "${stateDir}/templates";
  authentikEnvFile = "${stateDir}/authentik.env";
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

    image = lib.mkOption {
      type = lib.types.str;
      default = "ghcr.io/goauthentik/server:2025.10";
      description = "Container image used for the Authentik server and worker.";
    };
  };

  config = lib.mkIf cfg.enable {
    age.secrets.authentik_secret_key = {
      file = /root/secrets/authentik_secret_key.age;
      owner = "root";
      group = "root";
      mode = "0400";
    };

    age.secrets.authentik_postgresql_password = {
      file = /root/secrets/authentik_postgresql_password.age;
      owner = "root";
      group = "root";
      mode = "0400";
    };

    networking.firewall.allowedTCPPorts = [ 80 443 ];

    systemd.tmpfiles.rules = [
      "d ${stateDir} 0750 root root - -"
      "d ${dataDir} 0750 root root - -"
      "d ${templatesDir} 0750 root root - -"
    ];

    systemd.services.authentik-postgresql-init = {
      description = "Prepare PostgreSQL for Authentik";
      after = [ "postgresql.target" ];
      requires = [ "postgresql.target" ];
      before = [
        "authentik-bootstrap.service"
        "podman-authentik-server.service"
        "podman-authentik-worker.service"
      ];
      wantedBy = [ "multi-user.target" ];
      path = [ config.services.postgresql.package pkgs.gnugrep ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        User = "postgres";
        Group = "postgres";
        LoadCredential = [ "db_password:${config.age.secrets.authentik_postgresql_password.path}" ];
      };
      script = ''
        set -euo pipefail

        db_password="$(<"$CREDENTIALS_DIRECTORY/db_password")"
        db_password="''${db_password//\'/\'\'}"

        psql -tAc "SELECT 1 FROM pg_roles WHERE rolname = 'authentik'" | grep -q 1 || \
          psql -tAc 'CREATE ROLE "authentik" LOGIN'
        psql -tAc "ALTER ROLE \"authentik\" WITH LOGIN PASSWORD '$db_password'"
      '';
    };

    systemd.services.authentik-bootstrap = {
      description = "Prepare Authentik container environment";
      wantedBy = [ "multi-user.target" ];
      after = [ "authentik-postgresql-init.service" ];
      requires = [ "authentik-postgresql-init.service" ];
      before = [
        "podman-authentik-server.service"
        "podman-authentik-worker.service"
      ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
      };
      script = ''
        set -euo pipefail

        ${pkgs.coreutils}/bin/install -d -m 0750 ${stateDir} ${dataDir} ${templatesDir}

        secret_key="$(${pkgs.coreutils}/bin/tr -d '\n' < ${config.age.secrets.authentik_secret_key.path})"
        db_password="$(${pkgs.coreutils}/bin/tr -d '\n' < ${config.age.secrets.authentik_postgresql_password.path})"

        umask 077
        : > ${authentikEnvFile}
        ${pkgs.coreutils}/bin/chmod 0600 ${authentikEnvFile}

        ${pkgs.coreutils}/bin/printf '%s\n' 'AUTHENTIK_POSTGRESQL__HOST=host.containers.internal' >> ${authentikEnvFile}
        ${pkgs.coreutils}/bin/printf '%s\n' 'AUTHENTIK_POSTGRESQL__NAME=authentik' >> ${authentikEnvFile}
        ${pkgs.coreutils}/bin/printf '%s\n' 'AUTHENTIK_POSTGRESQL__USER=authentik' >> ${authentikEnvFile}
        ${pkgs.coreutils}/bin/printf '%s\n' 'AUTHENTIK_POSTGRESQL__PORT=5432' >> ${authentikEnvFile}
        ${pkgs.coreutils}/bin/printf 'AUTHENTIK_POSTGRESQL__PASSWORD=%s\n' "$db_password" >> ${authentikEnvFile}
        ${pkgs.coreutils}/bin/printf 'AUTHENTIK_SECRET_KEY=%s\n' "$secret_key" >> ${authentikEnvFile}
      '';
    };

    systemd.services.podman-authentik-server = {
      after = [ "authentik-bootstrap.service" ];
      requires = [ "authentik-bootstrap.service" ];
    };

    systemd.services.podman-authentik-worker = {
      after = [ "authentik-bootstrap.service" ];
      requires = [ "authentik-bootstrap.service" ];
    };

    virtualisation.oci-containers.containers = {
      authentik-server = {
        image = cfg.image;
        autoStart = true;
        cmd = [ "server" ];
        environmentFiles = [ authentikEnvFile ];
        extraOptions = [ "--network=podman" "--shm-size=512m" ];
        ports = [ "127.0.0.1:${toString cfg.port}:9000" ];
        volumes = [
          "${dataDir}:/data:U"
          "${templatesDir}:/templates:U"
        ];
      };

      authentik-worker = {
        image = cfg.image;
        autoStart = true;
        cmd = [ "worker" ];
        environmentFiles = [ authentikEnvFile ];
        extraOptions = [ "--network=podman" "--shm-size=512m" ];
        volumes = [
          "${dataDir}:/data:U"
          "${templatesDir}:/templates:U"
        ];
      };
    };

    services.postgresql = {
      enable = true;
      enableTCPIP = true;
      authentication = lib.mkBefore ''
        host authentik authentik 10.88.0.0/16 scram-sha-256
      '';
      ensureDatabases = [ "authentik" ];
      ensureUsers = [
        {
          name = "authentik";
          ensureDBOwnership = true;
          ensureClauses = {
            login = true;
          };
        }
      ];
      settings.listen_addresses = lib.mkDefault "127.0.0.1,10.88.0.1";
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