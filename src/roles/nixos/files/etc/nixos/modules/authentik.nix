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
    "AUTHENTIK_POSTGRESQL__HOST": "authentik-postgresql",
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

    postgresqlPort = lib.mkOption {
      type = lib.types.port;
      default = 5433;
      description = "Host port for Authentik PostgreSQL container (maps to 5432 inside container).";
    };

    postgresqlImage = lib.mkOption {
      type = lib.types.str;
      default = "postgres:16-alpine";
      description = "Container image used for PostgreSQL.";
    };

    postgresqlDataDir = lib.mkOption {
      type = lib.types.path;
      default = "${stateDir}/postgresql-data";
      description = "Directory for PostgreSQL data persistence.";
    };

    postgresqlMemoryLimit = lib.mkOption {
      type = lib.types.str;
      default = "2g";
      description = "Memory limit for PostgreSQL container.";
    };

    postgresqlCpuLimit = lib.mkOption {
      type = lib.types.str;
      default = "1.0";
      description = "CPU limit for PostgreSQL container (in cores).";
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
        mode = "0444";
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
        "d ${cfg.postgresqlDataDir} 0700 root root - -"
      ];

      systemd.services.authentik-prepare-env = {
        description = "Prepare Authentik environment file";
        unitConfig.DefaultDependencies = false;
        serviceConfig = {
          Type = "oneshot";
          ExecStart = authentikPrepareEnvScript;
        };
      };

      systemd.services.podman-authentik-server = {
        after = [ "podman-postgresql.service" ];
        requires = [ "podman-postgresql.service" "authentik-prepare-env.service" ];
      };

      systemd.services.podman-authentik-worker = {
        after = [ "podman-postgresql.service" ];
        requires = [ "podman-postgresql.service" "authentik-prepare-env.service" ];
      };

      virtualisation.oci-containers.containers = {
        authentik-postgresql = {
          image = cfg.postgresqlImage;
          autoStart = true;
          environment = {
            POSTGRES_USER = "authentik";
            POSTGRES_PASSWORD_FILE = "${config.age.secrets.authentik_postgresql_password.path}";
            POSTGRES_DB = "authentik";
          };
          extraOptions = [
            "--memory=${cfg.postgresqlMemoryLimit}"
            "--cpus=${cfg.postgresqlCpuLimit}"
            "--health-cmd=sh -c \"pg_isready -U authentik -d authentik\""
            "--health-interval=10s"
            "--health-timeout=5s"
            "--health-retries=3"
            "--health-start-period=30s"
          ];
          ports = [ "${toString cfg.postgresqlPort}:5432" ];
          volumes = [
            "${cfg.postgresqlDataDir}:/var/lib/postgresql/data:U"
            "${config.age.secrets.authentik_postgresql_password.path}:${config.age.secrets.authentik_postgresql_password.path}:ro"
          ];
        };

        authentik-server = {
          image = cfg.image;
          autoStart = true;
          cmd = [ "server" ];
          environmentFiles = [ authentikEnvFile ];
          extraOptions = [ "--shm-size=512m" ];
          ports = [ "127.0.0.1:${toString cfg.port}:9000" ];
          volumes = [
            "${dataDir}:/data:U"
            "${templatesDir}:/templates:U"
            "${config.age.secrets.authentik_secret_key.path}:${config.age.secrets.authentik_secret_key.path}:ro"
            "${config.age.secrets.authentik_postgresql_password.path}:${config.age.secrets.authentik_postgresql_password.path}:ro"
            "${config.age.secrets.authentik_admin_password.path}:${config.age.secrets.authentik_admin_password.path}:ro"
            "${config.age.secrets.authentik_bootstrap_token.path}:${config.age.secrets.authentik_bootstrap_token.path}:ro"
          ];
        };

        authentik-worker = {
          image = cfg.image;
          autoStart = true;
          cmd = [ "worker" ];
          environmentFiles = [ authentikEnvFile ];
          extraOptions = [ "--shm-size=512m" ];
          volumes = [
            "${dataDir}:/data:U"
            "${templatesDir}:/templates:U"
            "${config.age.secrets.authentik_secret_key.path}:${config.age.secrets.authentik_secret_key.path}:ro"
            "${config.age.secrets.authentik_postgresql_password.path}:${config.age.secrets.authentik_postgresql_password.path}:ro"
            "${config.age.secrets.authentik_admin_password.path}:${config.age.secrets.authentik_admin_password.path}:ro"
            "${config.age.secrets.authentik_bootstrap_token.path}:${config.age.secrets.authentik_bootstrap_token.path}:ro"
          ];
        };
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
      system.activationScripts.authentikCleanup.text = let
        escapedSecretFiles = lib.concatMapStringsSep " " lib.escapeShellArg authentikSecretFiles;
      in ''
        set -euo pipefail

        systemctl=${config.systemd.package}/bin/systemctl
        podman=${pkgs.podman}/bin/podman

        "$systemctl" stop \
          podman-authentik-server.service \
          podman-authentik-worker.service \
          podman-authentik-postgresql.service \
          authentik-prepare-env.service \
          || true

        "$podman" rm -f authentik-server authentik-worker authentik-postgresql >/dev/null 2>&1 || true
        "$podman" image rm ${lib.escapeShellArg cfg.image} ${lib.escapeShellArg cfg.postgresqlImage} >/dev/null 2>&1 || true

        rm -rf ${lib.escapeShellArg stateDir}
        rm -f ${escapedSecretFiles}

        "$systemctl" reset-failed \
          podman-authentik-server.service \
          podman-authentik-worker.service \
          podman-authentik-postgresql.service \
          authentik-prepare-env.service \
          >/dev/null 2>&1 || true
      '';
    })
  ];
}