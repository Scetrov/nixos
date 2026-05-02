{ config, lib, pkgs, ... }:

let
  cfg = config.scetrov.services.authentik;
  stateDir = "/var/lib/authentik";
  dataDir = "${stateDir}/data";
  templatesDir = "${stateDir}/templates";
  authentikEnvFile = "${stateDir}/authentik.env";
  authentikSecretFiles = [
    "/root/secrets/authentik_admin_user.age"
    "/root/secrets/authentik_admin_password.age"
    "/root/secrets/authentik_bootstrap_token.age"
    "/root/secrets/authentik_postgresql_password.age"
    "/root/secrets/authentik_secret_key.age"
    "/root/secrets/grafana_authentik_client_id.age"
    "/root/secrets/grafana_authentik_client_secret.age"
  ];
  authentikPrepareEnvScript = pkgs.writeShellScript "authentik-prepare-env" ''
    set -euo pipefail

    ${pkgs.coreutils}/bin/install -d -m 0750 ${stateDir} ${dataDir} ${templatesDir}

    export AUTHENTIK_ENV_FILE=${authentikEnvFile}
    export AUTHENTIK_SECRET_KEY_FILE=${config.age.secrets.authentik_secret_key.path}
    export AUTHENTIK_POSTGRESQL_PASSWORD_FILE=${config.age.secrets.authentik_postgresql_password.path}
    export AUTHENTIK_BOOTSTRAP_PASSWORD_FILE=${config.age.secrets.authentik_admin_password.path}
    export AUTHENTIK_BOOTSTRAP_TOKEN_FILE=${config.age.secrets.authentik_bootstrap_token.path}

    ${pkgs.python3}/bin/python3 <<'PY'
import os
import tempfile
from pathlib import Path


def read_secret(name: str, env_var: str) -> str:
    value = Path(os.environ[env_var]).read_text()
    value = value.rstrip("\r\n")
    if "\n" in value or "\r" in value:
        raise SystemExit(f"{name} contains embedded newlines, which are not supported in Podman environment files")
    return value


env_path = Path(os.environ["AUTHENTIK_ENV_FILE"])
entries = {
    "AUTHENTIK_POSTGRESQL__HOST": "host.containers.internal",
    "AUTHENTIK_POSTGRESQL__NAME": "authentik",
    "AUTHENTIK_POSTGRESQL__USER": "authentik",
    "AUTHENTIK_POSTGRESQL__PORT": "5432",
    "AUTHENTIK_POSTGRESQL__PASSWORD": read_secret("AUTHENTIK_POSTGRESQL__PASSWORD", "AUTHENTIK_POSTGRESQL_PASSWORD_FILE"),
    "AUTHENTIK_BOOTSTRAP_PASSWORD": read_secret("AUTHENTIK_BOOTSTRAP_PASSWORD", "AUTHENTIK_BOOTSTRAP_PASSWORD_FILE"),
    "AUTHENTIK_BOOTSTRAP_TOKEN": read_secret("AUTHENTIK_BOOTSTRAP_TOKEN", "AUTHENTIK_BOOTSTRAP_TOKEN_FILE"),
    "AUTHENTIK_SECRET_KEY": read_secret("AUTHENTIK_SECRET_KEY", "AUTHENTIK_SECRET_KEY_FILE"),
}

with tempfile.NamedTemporaryFile("w", dir=env_path.parent, delete=False, encoding="utf-8") as handle:
    for key, value in entries.items():
        handle.write(f"{key}={value}\n")
    temp_path = Path(handle.name)

temp_path.chmod(0o600)
temp_path.replace(env_path)
PY
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

    image = lib.mkOption {
      type = lib.types.str;
      default = "ghcr.io/goauthentik/server:2025.10";
      description = "Container image used for the Authentik server and worker.";
    };
  };

  config = lib.mkMerge [
    (lib.mkIf cfg.enable {
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

      age.secrets.authentik_admin_user = {
        file = /root/secrets/authentik_admin_user.age;
        owner = "root";
        group = "root";
        mode = "0400";
      };

      age.secrets.authentik_admin_password = {
        file = /root/secrets/authentik_admin_password.age;
        owner = "root";
        group = "root";
        mode = "0400";
      };

      age.secrets.authentik_bootstrap_token = {
        file = /root/secrets/authentik_bootstrap_token.age;
        owner = "root";
        group = "root";
        mode = "0400";
      };

      age.secrets.grafana_authentik_client_id = {
        file = /root/secrets/grafana_authentik_client_id.age;
        owner = "root";
        group = "root";
        mode = "0400";
      };

      age.secrets.grafana_authentik_client_secret = {
        file = /root/secrets/grafana_authentik_client_secret.age;
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
          psql -tAc "SELECT 1 FROM pg_database WHERE datname = 'authentik'" | grep -q 1 || \
            psql -tAc 'CREATE DATABASE "authentik" OWNER "authentik"'
          psql -tAc 'ALTER DATABASE "authentik" OWNER TO "authentik"'
          psql -tAc 'GRANT ALL PRIVILEGES ON DATABASE "authentik" TO "authentik"'
          psql -d authentik -tAc 'ALTER SCHEMA public OWNER TO "authentik"'
          psql -d authentik -tAc 'GRANT ALL ON SCHEMA public TO "authentik"'
        '';
      };

      systemd.services.podman-authentik-server = {
        after = [ "authentik-postgresql-init.service" ];
        requires = [ "authentik-postgresql-init.service" ];
        serviceConfig.ExecStartPre = [ authentikPrepareEnvScript ];
      };

      systemd.services.podman-authentik-worker = {
        after = [ "authentik-postgresql-init.service" ];
        requires = [ "authentik-postgresql-init.service" ];
        serviceConfig.ExecStartPre = [ authentikPrepareEnvScript ];
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
    })

    (lib.mkIf (!cfg.enable) {
      # Disable PostgreSQL if only Authentik was using it
      services.postgresql.enable = lib.mkDefault false;
      
      system.activationScripts.authentikCleanup.text = let
        escapedSecretFiles = lib.concatMapStringsSep " " lib.escapeShellArg authentikSecretFiles;
      in ''
        set -euo pipefail

        systemctl=${config.systemd.package}/bin/systemctl
        podman=${pkgs.podman}/bin/podman
        psql=${pkgs.postgresql}/bin/psql

        "$systemctl" stop \
          podman-authentik-server.service \
          podman-authentik-worker.service \
          authentik-postgresql-init.service \
          || true

        "$podman" rm -f authentik-server authentik-worker >/dev/null 2>&1 || true
        "$podman" image rm ${lib.escapeShellArg cfg.image} >/dev/null 2>&1 || true

        rm -rf ${lib.escapeShellArg stateDir}
        rm -f ${escapedSecretFiles}

        # Always clean up Authentik database/role when disabled
        if "$systemctl" is-active --quiet postgresql.service; then
          runuser -u postgres -- "$psql" -d postgres -v ON_ERROR_STOP=1 \
            -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'authentik' AND pid <> pg_backend_pid();" \
            >/dev/null
          runuser -u postgres -- "$psql" -d postgres -v ON_ERROR_STOP=1 \
            -c 'DROP DATABASE IF EXISTS "authentik";' \
            >/dev/null
          runuser -u postgres -- "$psql" -d postgres -v ON_ERROR_STOP=1 \
            -c 'DROP ROLE IF EXISTS "authentik";' \
            >/dev/null
        fi

        "$systemctl" stop postgresql.service >/dev/null 2>&1 || true
        rm -rf /var/lib/postgresql

        "$systemctl" reset-failed \
          podman-authentik-server.service \
          podman-authentik-worker.service \
          authentik-postgresql-init.service \
          postgresql.service \
          >/dev/null 2>&1 || true
      '';
    };
    })
  ];
}