{ config, lib, pkgs, ... }:

let
  cfg = config.scetrov.services.dependency-track;
  stateDir = "/var/lib/dependency-track";
  dataDir = "${stateDir}/data";
  postgresqlDataDir = "${stateDir}/postgresql-data";
  apiserverEnvFile = "${stateDir}/apiserver.env";
  
  apiserverPrepareEnvScript = pkgs.writeShellScript "dtrack-apiserver-prepare-env" ''
    set -euo pipefail

    ${pkgs.coreutils}/bin/install -d -m 0750 ${stateDir} ${dataDir} ${postgresqlDataDir}

    export DTRACK_ENV_FILE=${apiserverEnvFile}
    export DTRACK_DB_PASSWORD_FILE=${config.age.secrets.dtrack_db_password.path}
    export DTRACK_GITHUB_PAT_FILE=${config.age.secrets.dtrack_github_pat.path}
    export DTRACK_NVD_API_KEY_FILE=${config.age.secrets.dtrack_nvd_api_key.path}
    export DTRACK_OIDC_CLIENT_ID_FILE=${config.age.secrets.dtrack_oidc_client_id.path}

    ${pkgs.python3}/bin/python3 <<'PY'
import os
import tempfile
from pathlib import Path

def read_secret(name: str, path_var: str) -> str:
    path = os.environ.get(path_var)
    if not path or not Path(path).exists():
        return ""
    value = Path(path).read_text().strip()
    return value

env_path = Path(os.environ["DTRACK_ENV_FILE"])

# DB Config
db_pass = read_secret("DB_PASSWORD", "DTRACK_DB_PASSWORD_FILE")
github_pat = read_secret("GITHUB_PAT", "DTRACK_GITHUB_PAT_FILE")
nvd_key = read_secret("NVD_API_KEY", "DTRACK_NVD_API_KEY_FILE")
oidc_client_id = read_secret("OIDC_CLIENT_ID", "DTRACK_OIDC_CLIENT_ID_FILE")

entries = {
    "ALPINE_DATABASE_MODE": "external",
    "ALPINE_DATABASE_URL": "jdbc:postgresql://dtrack-db:5432/dtrack",
    "ALPINE_DATABASE_DRIVER": "org.postgresql.Driver",
    "ALPINE_DATABASE_USERNAME": "dtrack",
    "ALPINE_DATABASE_PASSWORD": db_pass,
    "ALPINE_DATABASE_POOL_ENABLED": "true",
    "ALPINE_DATABASE_POOL_MAX_SIZE": "20",
    "ALPINE_METRICS_ENABLED": "true",
    "ALPINE_OIDC_ENABLED": "true",
    "ALPINE_OIDC_ISSUER": "https://identity.net.scetrov.live/application/o/dependency-track/",
    "ALPINE_OIDC_CLIENT_ID": oidc_client_id,
    "ALPINE_OIDC_USERNAME_CLAIM": "preferred_username",
    "ALPINE_OIDC_USER_PROVISIONING": "true",
    "ALPINE_OIDC_TEAM_PROVISIONING": "true",
}

if github_pat:
    entries["GITHUB_REPOS_TOKEN"] = github_pat

if nvd_key:
    entries["VULNERABILITY_SOURCE_NVD_API_KEY"] = nvd_key

with tempfile.NamedTemporaryFile("w", dir=env_path.parent, delete=False, encoding="utf-8") as handle:
    for key, value in entries.items():
        handle.write(f"{key}={value}\n")
    temp_path = Path(handle.name)

temp_path.chmod(0o600)
temp_path.replace(env_path)
PY
  '';

  frontendEnvFile = "${stateDir}/frontend.env";
  frontendPrepareEnvScript = pkgs.writeShellScript "dtrack-frontend-prepare-env" ''
    set -euo pipefail

    export DTRACK_FRONTEND_ENV_FILE=${frontendEnvFile}
    export DTRACK_OIDC_CLIENT_ID_FILE=${config.age.secrets.dtrack_oidc_client_id.path}

    ${pkgs.python3}/bin/python3 <<'PY'
import os
import tempfile
from pathlib import Path

def read_secret(name: str, path_var: str) -> str:
    path = os.environ.get(path_var)
    if not path or not Path(path).exists():
        return ""
    value = Path(path).read_text().strip()
    return value

env_path = Path(os.environ["DTRACK_FRONTEND_ENV_FILE"])
oidc_client_id = read_secret("OIDC_CLIENT_ID", "DTRACK_OIDC_CLIENT_ID_FILE")

entries = {
    "API_BASE_URL": "https://${cfg.apiDomain}",
    "OIDC_ISSUER": "https://identity.net.scetrov.live/application/o/dependency-track/",
    "OIDC_CLIENT_ID": oidc_client_id,
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
  options.scetrov.services.dependency-track = {
    enable = lib.mkEnableOption "OWASP Dependency Track";

    domain = lib.mkOption {
      type = lib.types.str;
      default = "dtrack.net.scetrov.live";
      description = "Domain for Dependency Track Frontend.";
    };

    apiDomain = lib.mkOption {
      type = lib.types.str;
      default = "dtrack-api.net.scetrov.live";
      description = "Domain for Dependency Track API Server.";
    };

    apiPort = lib.mkOption {
      type = lib.types.port;
      default = 8081;
      description = "Local port for API server.";
    };

    frontendPort = lib.mkOption {
      type = lib.types.port;
      default = 8082;
      description = "Local port for Frontend.";
    };

    apiserverImage = lib.mkOption {
      type = lib.types.str;
      default = "dependencytrack/apiserver:4.12";
      description = "Container image for API Server.";
    };

    frontendImage = lib.mkOption {
      type = lib.types.str;
      default = "dependencytrack/frontend:4.12";
      description = "Container image for Frontend.";
    };

    postgresqlImage = lib.mkOption {
      type = lib.types.str;
      default = "postgres:16-alpine";
      description = "Container image for PostgreSQL.";
    };
  };

  config = lib.mkIf cfg.enable {
    age.secrets.dtrack_db_password = {
      file = /root/secrets/dtrack_db_password.age;
      owner = "root";
    };
    age.secrets.dtrack_github_pat = {
      file = /root/secrets/dtrack_github_pat.age;
      owner = "root";
    };
    age.secrets.dtrack_nvd_api_key = {
      file = /root/secrets/dtrack_nvd_api_key.age;
      owner = "root";
    };
    age.secrets.dtrack_oidc_client_id = {
      file = /root/secrets/dtrack_oidc_client_id.age;
      owner = "root";
    };
    age.secrets.dtrack_oidc_client_secret = {
      file = /root/secrets/dtrack_oidc_client_secret.age;
      owner = "root";
    };

    systemd.services.dtrack-apiserver-prepare-env = {
      description = "Prepare Dependency Track API Server environment file";
      wantedBy = [ "multi-user.target" ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        ExecStart = apiserverPrepareEnvScript;
      };
    };

    systemd.services.dtrack-frontend-prepare-env = {
      description = "Prepare Dependency Track Frontend environment file";
      wantedBy = [ "multi-user.target" ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        ExecStart = frontendPrepareEnvScript;
      };
    };

    systemd.services.dtrack-network = {
      description = "Create dependency-track Podman network";
      before = [
        "podman-dtrack-db.service"
        "podman-dtrack-apiserver.service"
        "podman-dtrack-frontend.service"
      ];
      wantedBy = [ "multi-user.target" ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        ExecStart = "${pkgs.podman}/bin/podman network create --ignore dtrack";
        ExecStop = "${pkgs.podman}/bin/podman network rm -f dtrack";
      };
    };

    virtualisation.oci-containers.containers = {
      dtrack-db = {
        image = cfg.postgresqlImage;
        autoStart = true;
        extraOptions = [ "--network=dtrack" ];
        environment = {
          POSTGRES_USER = "dtrack";
          POSTGRES_DB = "dtrack";
          POSTGRES_PASSWORD_FILE = "${config.age.secrets.dtrack_db_password.path}";
        };
        volumes = [
          "${postgresqlDataDir}:/var/lib/postgresql/data:U"
          "${config.age.secrets.dtrack_db_password.path}:${config.age.secrets.dtrack_db_password.path}:ro"
        ];
      };

      dtrack-apiserver = {
        image = cfg.apiserverImage;
        autoStart = true;
        environmentFiles = [ apiserverEnvFile ];
        extraOptions = [ 
          "--network=dtrack"
          "--memory=4g"
          "--cpus=2.0"
        ];
        ports = [ "127.0.0.1:${toString cfg.apiPort}:8080" ];
        volumes = [
          "${dataDir}:/data:U"
        ];
        dependsOn = [ "dtrack-db" ];
      };

      dtrack-frontend = {
        image = cfg.frontendImage;
        autoStart = true;
        environmentFiles = [ frontendEnvFile ];
        extraOptions = [ "--network=dtrack" ];
        ports = [ "127.0.0.1:${toString cfg.frontendPort}:8080" ];
        dependsOn = [ "dtrack-apiserver" ];
      };
    };

    services.caddy.virtualHosts = {
      "${cfg.domain}" = {
        useACMEHost = "scetrov.live";
        extraConfig = ''
          encode zstd gzip
          reverse_proxy 127.0.0.1:${toString cfg.frontendPort}
        '';
      };
      "${cfg.apiDomain}" = {
        useACMEHost = "scetrov.live";
        extraConfig = ''
          encode zstd gzip
          reverse_proxy 127.0.0.1:${toString cfg.apiPort}
        '';
      };
    };
  };
}
