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
  schemaResetMarkerFile = "${stateDir}/schema-reset-generation";
  schemaResetGeneration =
    if cfg.resetSchemaGeneration == null then "" else toString cfg.resetSchemaGeneration;
  defaultSuiRpcUrl =
    if cfg.suiNetwork == "mainnet" then
      "https://fullnode.mainnet.sui.io:443"
    else
      "https://fullnode.testnet.sui.io:443";
  chainHeadExporterScript = pkgs.writeText "frontier-indexer-chain-head-exporter.py" ''
    import json
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.error import URLError
    from urllib.request import Request, urlopen

    RPC_URL = ${builtins.toJSON cfg.suiRpcUrl}
    NETWORK = ${builtins.toJSON cfg.suiNetwork}
    PORT = ${toString cfg.chainHeadMetricsPort}

    def render_metrics():
      labels = '{service="frontier-indexer",network="%s"}' % NETWORK
      lines = [
        "# HELP frontier_indexer_chain_head_scrape_success Whether the Sui chain head scrape succeeded.",
        "# TYPE frontier_indexer_chain_head_scrape_success gauge",
      ]

      payload = json.dumps(
        {
          "jsonrpc": "2.0",
          "id": 1,
          "method": "sui_getLatestCheckpointSequenceNumber",
          "params": [],
        }
      ).encode()
      request = Request(
        RPC_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
      )

      try:
        with urlopen(request, timeout=10) as response:
          body = json.load(response)
        checkpoint = int(body["result"])
        lines.extend(
          [
            "# HELP frontier_indexer_chain_head_checkpoint Latest Sui checkpoint at the configured chain head.",
            "# TYPE frontier_indexer_chain_head_checkpoint gauge",
            f"frontier_indexer_chain_head_checkpoint{labels} {checkpoint}",
            f"frontier_indexer_chain_head_scrape_success{labels} 1",
          ]
        )
      except (KeyError, TypeError, ValueError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        lines.append(f"frontier_indexer_chain_head_scrape_success{labels} 0")

      return "\n".join(lines) + "\n"

    class Handler(BaseHTTPRequestHandler):
      def do_GET(self):
        if self.path != "/metrics":
          self.send_response(404)
          self.end_headers()
          return

        payload = render_metrics().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

      def log_message(self, format, *args):
        return

    if __name__ == "__main__":
      ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
  '';
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
      printf 'INGESTION_SOURCE=%s\n' ${lib.escapeShellArg cfg.ingestionSource}
      ${lib.optionalString (cfg.ingestConcurrencyMax != null) ''
        printf 'INGEST_CONCURRENCY_MAX=%s\n' ${lib.escapeShellArg (toString cfg.ingestConcurrencyMax)}
      ''}
      ${lib.optionalString (cfg.firstCheckpoint != null) ''
        printf 'FIRST_CHECKPOINT=%s\n' ${lib.escapeShellArg cfg.firstCheckpoint}
      ''}
    } > ${indexerEnvFile}
  '';
  schemaResetScript = pkgs.writeShellScript "frontier-indexer-schema-reset" ''
    set -euo pipefail

    reset_generation=${lib.escapeShellArg schemaResetGeneration}
    if [ -z "$reset_generation" ]; then
      echo "Frontier Indexer schema reset skipped: no reset generation configured"
      exit 0
    fi

    if [ ! -s ${indexerEnvFile} ]; then
      echo "Frontier Indexer schema reset failed: missing indexer environment file ${indexerEnvFile}" >&2
      exit 1
    fi

    set -a
    . ${indexerEnvFile}
    set +a

    for key in DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD DB_SCHEMA; do
      if [ -z "''${!key:-}" ]; then
        echo "Frontier Indexer schema reset failed: required env key $key is empty" >&2
        exit 1
      fi
    done

    if [ "$DB_SCHEMA" != "indexer" ]; then
      echo "Frontier Indexer schema reset failed: refusing to reset unexpected schema '$DB_SCHEMA'" >&2
      exit 1
    fi

    if [ -s ${schemaResetMarkerFile} ] && [ "$(${pkgs.coreutils}/bin/cat ${schemaResetMarkerFile})" = "$reset_generation" ]; then
      echo "Frontier Indexer schema reset skipped: generation $reset_generation already applied"
      exit 0
    fi

    export PGPASSWORD="$DB_PASSWORD"
    ${pkgs.podman}/bin/podman run --rm \
      --network=${lib.escapeShellArg cfg.network} \
      --env PGPASSWORD \
      --entrypoint=psql \
      ${lib.escapeShellArg cfg.timescaleImage} \
      -h "$DB_HOST" \
      -p "$DB_PORT" \
      -U "$DB_USER" \
      -d "$DB_NAME" \
      -v ON_ERROR_STOP=1 \
      -v schema="$DB_SCHEMA" \
      -v owner="$DB_USER" <<'SQL'
    SELECT format('DROP SCHEMA IF EXISTS %I CASCADE', :'schema');
    \gexec
    SELECT format('CREATE SCHEMA %I AUTHORIZATION %I', :'schema', :'owner');
    \gexec
    SQL

    umask 027
    printf '%s' "$reset_generation" > ${schemaResetMarkerFile}
    echo "Frontier Indexer schema reset applied generation $reset_generation for schema=$DB_SCHEMA"
  '';
  dbPreflightScript = pkgs.writeShellScript "frontier-indexer-db-preflight" ''
        set -euo pipefail

        if [ ! -s ${indexerEnvFile} ]; then
          echo "Frontier Indexer database preflight failed: missing indexer environment file ${indexerEnvFile}" >&2
          exit 1
        fi

        if [ ! -s ${dbPasswordFile} ]; then
          echo "Frontier Indexer database preflight failed: missing database password file ${dbPasswordFile}" >&2
          exit 1
        fi

        set -a
        . ${indexerEnvFile}
        set +a

        for key in DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD DB_SCHEMA; do
          if [ -z "''${!key:-}" ]; then
            echo "Frontier Indexer database preflight failed: required env key $key is empty" >&2
            exit 1
          fi
        done

        test_connection() {
          ${pkgs.podman}/bin/podman run --rm \
            --network=${lib.escapeShellArg cfg.network} \
            --env PGPASSWORD \
            --entrypoint=psql \
            ${lib.escapeShellArg cfg.timescaleImage} \
            -h "$DB_HOST" \
            -p "$DB_PORT" \
            -U "$DB_USER" \
            -d "$DB_NAME" \
            -v ON_ERROR_STOP=1 \
            -Atc "select current_database(), current_user;" >/dev/null
        }

        export PGPASSWORD="$DB_PASSWORD"
        if test_connection; then
          echo "Frontier Indexer database preflight succeeded for host=$DB_HOST port=$DB_PORT database=$DB_NAME user=$DB_USER schema=$DB_SCHEMA"
          exit 0
        fi

        echo "Frontier Indexer database preflight: password authentication failed; synchronizing existing TimescaleDB role password from runtime secret" >&2
        ${pkgs.python3}/bin/python - ${dbPasswordFile} <<'PY' \
          | ${pkgs.podman}/bin/podman exec -i -u postgres frontier-timescaledb \
            psql -d postgres -v ON_ERROR_STOP=1 >/dev/null
    import sys
    password = open(sys.argv[1]).read().rstrip("\n")
    if "$frontier$" in password:
        raise SystemExit("unsupported delimiter in database password")
    print("ALTER USER postgres WITH PASSWORD $frontier$" + password + "$frontier$;")
    PY

        if test_connection; then
          echo "Frontier Indexer database preflight succeeded after synchronizing database role password"
          exit 0
        fi

        echo "Frontier Indexer database preflight failed: cannot authenticate to host=$DB_HOST port=$DB_PORT database=$DB_NAME user=$DB_USER from Podman network ${cfg.network}" >&2
        exit 1
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

    chainHeadMetricsPort = lib.mkOption {
      type = lib.types.port;
      default = 9185;
      description = "Local host port for the Sui chain head exporter used by Frontier Indexer dashboards.";
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
      default = "ghcr.io/ocky-public/frontier-indexer:v0.3.5";
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

    suiRpcUrl = lib.mkOption {
      type = lib.types.str;
      default = defaultSuiRpcUrl;
      description = "Sui JSON-RPC endpoint used to read the latest chain head checkpoint.";
    };

    firstCheckpoint = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "The first checkpoint sequence number to start indexing from.";
    };

    ingestionSource = lib.mkOption {
      type = lib.types.enum [
        "store"
        "fullnode"
        "local"
      ];
      default = "store";
      description = "Checkpoint ingestion mode used by Frontier Indexer.";
    };

    ingestConcurrencyMax = lib.mkOption {
      type = lib.types.nullOr lib.types.int;
      default = null;
      description = "Optional maximum checkpoint ingestion concurrency override.";
    };

    resetSchemaGeneration = lib.mkOption {
      type = lib.types.nullOr lib.types.int;
      default = null;
      description = "Optional schema reset generation. When set, the configured indexer schema is dropped and recreated once before the indexer starts.";
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

    systemd.services.frontier-indexer-chain-head-exporter = {
      description = "Expose the latest Sui chain head checkpoint for Frontier Indexer dashboards";
      wantedBy = [ "multi-user.target" ];
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
      serviceConfig = {
        ExecStart = "${pkgs.python3}/bin/python ${chainHeadExporterScript}";
        Restart = "always";
        RestartSec = "10s";
        DynamicUser = true;
        NoNewPrivileges = true;
        PrivateTmp = true;
        ProtectHome = true;
        ProtectSystem = "strict";
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
      before = [
        "frontier-indexer-schema-reset.service"
        "frontier-indexer-db-preflight.service"
      ];
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

    systemd.services.frontier-indexer-schema-reset = {
      description = "Reset Frontier Indexer schema for declared cycle generation";
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
      before = [
        "frontier-indexer-db-preflight.service"
        "podman-frontier-indexer.service"
      ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = schemaResetScript;
      };
    };

    systemd.services.frontier-indexer-db-preflight = {
      description = "Validate Frontier Indexer database setup";
      requires = [
        "frontier-indexer-prepare-env.service"
        "frontier-indexer-network.service"
        "podman-frontier-timescaledb.service"
        "frontier-indexer-wait-for-db.service"
        "frontier-indexer-schema-reset.service"
      ];
      after = [
        "frontier-indexer-prepare-env.service"
        "frontier-indexer-network.service"
        "podman-frontier-timescaledb.service"
        "frontier-indexer-wait-for-db.service"
        "frontier-indexer-schema-reset.service"
      ];
      before = [ "podman-frontier-indexer.service" ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = dbPreflightScript;
      };
    };

    systemd.services.podman-frontier-indexer = {
      requires = [
        "frontier-indexer-prepare-env.service"
        "frontier-indexer-network.service"
        "podman-frontier-timescaledb.service"
        "frontier-indexer-wait-for-db.service"
        "frontier-indexer-schema-reset.service"
        "frontier-indexer-db-preflight.service"
      ];
      after = [
        "frontier-indexer-prepare-env.service"
        "frontier-indexer-network.service"
        "podman-frontier-timescaledb.service"
        "frontier-indexer-wait-for-db.service"
        "frontier-indexer-schema-reset.service"
        "frontier-indexer-db-preflight.service"
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
      {
        job_name = "frontier-chain-head";
        metrics_path = "/metrics";
        static_configs = [
          {
            targets = [ "127.0.0.1:${toString cfg.chainHeadMetricsPort}" ];
            labels = {
              service = "frontier-indexer";
              network = cfg.suiNetwork;
            };
          }
        ];
      }
    ];
  };
}
