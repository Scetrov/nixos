{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.scetrov.services.frontier-indexer;
  stateDir = "/var/lib/frontier-indexer";
  timescaleDataDir = "${stateDir}/timescaledb-data";
  dbPasswordFile = "${stateDir}/db-password";
  indexerEnvFile = "${stateDir}/indexer.env";
  indexerPrepareEnvScript = pkgs.writeShellScript "frontier-indexer-prepare-env" ''
    set -euo pipefail

    ${pkgs.coreutils}/bin/install -d -m 0750 ${stateDir}
    ${pkgs.coreutils}/bin/install -m 0444 ${config.age.secrets.frontier_indexer_db_password.path} ${dbPasswordFile}

    db_password="$(${pkgs.coreutils}/bin/cat ${config.age.secrets.frontier_indexer_db_password.path})"
    umask 077
    {
      printf 'DB_HOST=frontier-timescaledb\n'
      printf 'DB_PORT=5432\n'
      printf 'DB_NAME=postgres\n'
      printf 'DB_USER=postgres\n'
      printf 'DB_PASSWORD=%s\n' "$db_password"
      printf 'DB_SCHEMA=indexer\n'
      printf 'SUI_NETWORK=%s\n' ${lib.escapeShellArg cfg.suiNetwork}
      printf 'PACKAGES=app,world\n'
      printf 'METRICS_ADDRESS=0.0.0.0:9184\n'
    } > ${indexerEnvFile}
  '';
in
{
  options.scetrov.services.frontier-indexer = {
    enable = lib.mkEnableOption "Frontier Indexer with TimescaleDB";

    databaseListenAddress = lib.mkOption {
      type = lib.types.str;
      default = "10.229.10.2";
      description = "Host address where TimescaleDB is published.";
    };

    databasePort = lib.mkOption {
      type = lib.types.port;
      default = 5432;
      description = "Host and container port for TimescaleDB.";
    };

    metricsPort = lib.mkOption {
      type = lib.types.port;
      default = 9184;
      description = "Local host port for Frontier Indexer Prometheus metrics.";
    };

    allowedDatabaseCidr = lib.mkOption {
      type = lib.types.str;
      default = "10.229.0.0/16";
      description = "Source CIDR allowed to connect to TimescaleDB.";
    };

    network = lib.mkOption {
      type = lib.types.str;
      default = "frontier-indexer";
      description = "Dedicated Podman network shared by Frontier Indexer containers.";
    };

    indexerImage = lib.mkOption {
      type = lib.types.str;
      default = "ghcr.io/ocky-public/frontier-indexer:v0.3.4";
      description = "Container image for Frontier Indexer.";
    };

    timescaleImage = lib.mkOption {
      type = lib.types.str;
      default = "docker.io/timescale/timescaledb-ha:pg17";
      description = "Container image for TimescaleDB.";
    };

    suiNetwork = lib.mkOption {
      type = lib.types.enum [
        "mainnet"
        "testnet"
      ];
      default = "testnet";
      description = "Sui network Frontier Indexer should process.";
    };
  };

  config = lib.mkIf cfg.enable {
    age.secrets.frontier_indexer_db_password = {
      file = /root/secrets/frontier_indexer_db_password.age;
      owner = "root";
    };

    systemd.tmpfiles.rules = [ "d ${stateDir} 0750 root root - -" ];

    systemd.services.frontier-indexer-prepare-env = {
      description = "Prepare Frontier Indexer environment file";
      wantedBy = [ "multi-user.target" ];
      before = [
        "podman-frontier-timescaledb.service"
        "podman-frontier-indexer.service"
      ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        ExecStart = indexerPrepareEnvScript;
      };
    };

    systemd.services.frontier-indexer-network = {
      description = "Create Frontier Indexer Podman network";
      before = [
        "podman-frontier-timescaledb.service"
        "frontier-indexer-wait-for-db.service"
        "podman-frontier-indexer.service"
      ];
      wantedBy = [ "multi-user.target" ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        ExecStart = "${pkgs.podman}/bin/podman network create --ignore ${lib.escapeShellArg cfg.network}";
        ExecStop = "${pkgs.podman}/bin/podman network rm -f ${lib.escapeShellArg cfg.network}";
      };
    };

    virtualisation.oci-containers.containers = {
      frontier-timescaledb = {
        image = cfg.timescaleImage;
        autoStart = true;
        extraOptions = [ "--network=${cfg.network}" ];
        ports = [ "${cfg.databaseListenAddress}:${toString cfg.databasePort}:5432" ];
        environment = {
          POSTGRES_USER = "postgres";
          POSTGRES_DB = "postgres";
          POSTGRES_PASSWORD_FILE = dbPasswordFile;
        };
        volumes = [
          "${timescaleDataDir}:/home/postgres/pgdata/data:U"
          "${dbPasswordFile}:${dbPasswordFile}:ro"
        ];
      };

      frontier-indexer = {
        image = cfg.indexerImage;
        autoStart = true;
        dependsOn = [ "frontier-timescaledb" ];
        extraOptions = [ "--network=${cfg.network}" ];
        ports = [ "127.0.0.1:${toString cfg.metricsPort}:9184" ];
        environmentFiles = [ indexerEnvFile ];
      };
    };

    systemd.services.podman-frontier-timescaledb = {
      requires = [
        "frontier-indexer-prepare-env.service"
        "frontier-indexer-network.service"
      ];
      after = [
        "frontier-indexer-prepare-env.service"
        "frontier-indexer-network.service"
      ];
      serviceConfig = {
        Restart = lib.mkForce "on-failure";
        RestartSec = "10s";
      };
    };

    systemd.services.frontier-indexer-wait-for-db = {
      description = "Wait for Frontier Indexer TimescaleDB";
      requires = [
        "frontier-indexer-network.service"
        "podman-frontier-timescaledb.service"
      ];
      after = [
        "frontier-indexer-network.service"
        "podman-frontier-timescaledb.service"
      ];
      before = [ "podman-frontier-indexer.service" ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = pkgs.writeShellScript "frontier-indexer-wait-for-db" ''
          set -euo pipefail

          for attempt in $(${pkgs.coreutils}/bin/seq 1 60); do
            if ${pkgs.podman}/bin/podman run --rm \
              --network=${lib.escapeShellArg cfg.network} \
              --entrypoint=pg_isready \
              ${lib.escapeShellArg cfg.timescaleImage} \
              -h frontier-timescaledb \
              -p 5432 \
              -U postgres; then
              exit 0
            fi
            ${pkgs.coreutils}/bin/sleep 2
          done

          exit 1
        '';
      };
    };

    systemd.services.podman-frontier-indexer = {
      requires = [
        "frontier-indexer-prepare-env.service"
        "frontier-indexer-network.service"
        "podman-frontier-timescaledb.service"
        "frontier-indexer-wait-for-db.service"
      ];
      after = [
        "frontier-indexer-prepare-env.service"
        "frontier-indexer-network.service"
        "podman-frontier-timescaledb.service"
        "frontier-indexer-wait-for-db.service"
      ];
      serviceConfig = {
        Restart = lib.mkForce "on-failure";
        RestartSec = "10s";
      };
    };

    networking.firewall.extraCommands = ''
      iptables -A nixos-fw -p tcp -s ${cfg.allowedDatabaseCidr} --dport ${toString cfg.databasePort} -j nixos-fw-accept
    '';
    networking.firewall.extraStopCommands = ''
      iptables -D nixos-fw -p tcp -s ${cfg.allowedDatabaseCidr} --dport ${toString cfg.databasePort} -j nixos-fw-accept 2>/dev/null || true
    '';

    services.prometheus.scrapeConfigs = lib.mkAfter [
      {
        job_name = "frontier-indexer";
        metrics_path = "/metrics";
        static_configs = [
          {
            targets = [ "127.0.0.1:${toString cfg.metricsPort}" ];
            labels = {
              service = "frontier-indexer";
            };
          }
        ];
      }
    ];
  };
}
