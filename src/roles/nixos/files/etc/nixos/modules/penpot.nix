{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.scetrov.services.penpot;
  stateDir = "/var/lib/penpot";
  domain = "penpot.net.scetrov.live";
  secretNames = [
    "penpot_db_password"
    "penpot_secret_key"
    "penpot_oidc_client_id"
    "penpot_oidc_client_secret"
  ];
  # disable-email-verification: SMTP is intentionally absent, so Penpot must
  # activate OIDC-registered profiles immediately instead of gating them on a
  # verification e-mail that can never be delivered (with the flag on, an
  # inactive profile would also be rejected as email-already-exists).
  flags = "enable-login-with-oidc enable-oidc-registration disable-registration disable-login-with-password disable-smtp disable-email-verification enable-secure-session-cookies disable-telemetry enable-mcp";
  commonEnvironment = {
    PENPOT_FLAGS = flags;
    PENPOT_PUBLIC_URI = "https://${domain}";
  };
  # Keep the release's own routing. Only disable request-bearing Nginx logs;
  # backend/MCP service logs remain available through the journal and Alloy.
  nginxTemplate = pkgs.runCommand "penpot-nginx-no-request-logs" { } ''
    ${pkgs.gnused}/bin/sed \
      -e 's#access_log /dev/stdout penpot_upstream;#access_log off;#' \
      -e 's#error_log /dev/stderr;#error_log /dev/null;#' \
      ${
        pkgs.fetchurl {
          url = "https://raw.githubusercontent.com/penpot/penpot/2.18.4/docker/images/files/nginx.conf.template";
          hash = "sha256-M53cEynjHR6MhVt8SLYteKkLxx1HQ8qffFleCMG8qNw=";
        }
      } > "$out"
  '';
  containerOptions = [
    "--network=penpot"
    "--log-driver=journald"
    "--no-healthcheck"
  ];
  secretFiles = map (name: config.age.secrets.${name}.file) secretNames;
in
{
  options.scetrov.services.penpot.enable =
    lib.mkEnableOption "Penpot with native OIDC and remote MCP";

  config = lib.mkIf cfg.enable {
    age.secrets = lib.genAttrs secretNames (name: {
      file = /root/secrets + "/${name}.age";
      mode = "0400";
    });

    systemd.tmpfiles.rules = [
      "d ${stateDir} 0700 root root -"
      # Podman :U owns these directories; later switches must not chown them back.
      "d ${stateDir}/postgres 0700 - - -"
      "d ${stateDir}/assets 0755 - - -"
    ];

    systemd.services = {
      penpot-prepare-env = {
        description = "Prepare Penpot runtime secrets";
        restartTriggers = secretFiles;
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
          UMask = "0077";
          LoadCredential = map (name: "${name}:${config.age.secrets.${name}.path}") secretNames;
          ExecStart = "${pkgs.python3}/bin/python3 ${./penpot-prepare-env.py}";
        };
      };

      penpot-network = {
        description = "Create private Penpot Podman bridge";
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
          ExecStart = "${pkgs.podman}/bin/podman network create --ignore penpot";
        };
      };

    }
    //
      lib.genAttrs
        (map (name: "podman-penpot-${name}") [
          "postgres"
          "valkey"
          "backend"
          "frontend"
          "exporter"
          "mcp"
        ])
        (_: {
          requires = [
            "penpot-network.service"
            "penpot-prepare-env.service"
          ];
          after = [
            "penpot-network.service"
            "penpot-prepare-env.service"
          ];
          restartTriggers = secretFiles;
        });

    virtualisation.oci-containers.backend = "podman";
    virtualisation.oci-containers.containers = {
      penpot-postgres = {
        image = "docker.io/library/postgres:15.18-bookworm@sha256:e8db9bd3e9e1751eb639fb17be53cc6d1b62a322adf75b99e791767a7a16ce69";
        environment = {
          POSTGRES_USER = "penpot";
          POSTGRES_DB = "penpot";
          POSTGRES_INITDB_ARGS = "--data-checksums";
        };
        environmentFiles = [ "${stateDir}/postgres.env" ];
        volumes = [ "${stateDir}/postgres:/var/lib/postgresql/data:U" ];
        extraOptions = containerOptions ++ [
          "--memory=1g"
          "--cpus=1"
        ];
      };
      penpot-valkey = {
        image = "docker.io/valkey/valkey:8.1.10@sha256:640c5e62cea04b6d6f2084232651d0cc70362d31f4f805e7be94dbed6855e8f2";
        cmd = [
          "valkey-server"
          "--maxmemory"
          "128mb"
          "--maxmemory-policy"
          "volatile-lfu"
        ];
        extraOptions = containerOptions ++ [
          "--memory=256m"
          "--cpus=0.5"
        ];
      };
      penpot-backend = {
        image = "docker.io/penpotapp/backend:2.18.4@sha256:4a3821b66d5f1c473760911c3e445ff736d9b5274376e8f6ec8d0a3944df79a1";
        dependsOn = [
          "penpot-postgres"
          "penpot-valkey"
        ];
        environmentFiles = [ "${stateDir}/backend.env" ];
        environment = commonEnvironment // {
          PENPOT_DATABASE_URI = "postgresql://penpot-postgres/penpot";
          PENPOT_DATABASE_USERNAME = "penpot";
          PENPOT_REDIS_URI = "redis://penpot-valkey/0";
          PENPOT_OBJECTS_STORAGE_BACKEND = "fs";
          PENPOT_OBJECTS_STORAGE_FS_DIRECTORY = "/opt/data/assets";
          PENPOT_TELEMETRY_ENABLED = "false";
          PENPOT_OIDC_BASE_URI = "https://identity.net.scetrov.live/application/o/penpot/";
          PENPOT_OIDC_SCOPES = "openid profile email";
          # Penpot 2.15+ SSRF guard blocks the host-gateway-resolved identity
          # host (private IP) during OIDC discovery; allowlist it explicitly.
          PENPOT_SSRF_ALLOWED_HOSTS = "identity.net.scetrov.live";
        };
        volumes = [
          "${stateDir}/assets:/opt/data/assets:U"
          "/etc/ssl/certs/ca-certificates.crt:/etc/ssl/certs/ca-certificates.crt:ro"
        ];
        extraOptions = containerOptions ++ [
          "--memory=4g"
          "--cpus=2"
          "--add-host=identity.net.scetrov.live:host-gateway"
        ];
      };
      penpot-exporter = {
        image = "docker.io/penpotapp/exporter:2.18.4@sha256:3394056911fc35fd4738f21d6ffef5fbf07312418f3cb0e43dca4a3d04b9b8b2";
        dependsOn = [ "penpot-valkey" ];
        environmentFiles = [ "${stateDir}/exporter.env" ];
        environment = commonEnvironment // {
          PENPOT_INTERNAL_URI = "http://penpot-frontend:8080";
          PENPOT_REDIS_URI = "redis://penpot-valkey/0";
        };
        extraOptions = containerOptions ++ [
          "--memory=1g"
          "--cpus=1"
        ];
      };
      penpot-mcp = {
        image = "docker.io/penpotapp/mcp:2.18.4@sha256:1d6878c698affccfa1eef9944a2125b179f689ee04e51e5d3864be2ed747fae9";
        # The official image starts with --multi-user (remote mode, no filesystem tools).
        environment.PENPOT_MCP_REMOTE_MODE = "true";
        extraOptions = containerOptions ++ [
          "--memory=512m"
          "--cpus=0.5"
        ];
      };
      penpot-frontend = {
        image = "docker.io/penpotapp/frontend:2.18.4@sha256:e36e1e4eacd08173792dff27fefdb5427cd6938aeaeaf70585cf5cb8024d6211";
        dependsOn = [
          "penpot-backend"
          "penpot-exporter"
          "penpot-mcp"
        ];
        environmentFiles = [ "${stateDir}/frontend.env" ];
        environment = commonEnvironment;
        ports = [ "127.0.0.1:9011:8080" ];
        volumes = [
          "${stateDir}/assets:/opt/data/assets:ro"
          "${nginxTemplate}:/tmp/nginx.conf.template:ro"
        ];
        extraOptions = containerOptions ++ [
          "--memory=256m"
          "--cpus=0.5"
        ];
      };
    };

    services.caddy.virtualHosts.${domain} = {
      useACMEHost = "scetrov.live";
      logFormat = null;
      extraConfig = ''
        # Native OIDC and MCP-key authentication; no forward_auth here.
        reverse_proxy 127.0.0.1:9011
      '';
    };
    # Runtime proxy errors also contain request URIs. Remove the native MCP key
    # there, not just from access logs. Preserve the existing ERROR log level.
    services.caddy.logFormat = ''
      level ERROR
      format filter {
        wrap json
        fields {
          request>uri query {
            delete userToken
          }
          request>headers>Referer delete
        }
      }
    '';

    services.prometheus.scrapeConfigs = lib.mkAfter [
      {
        job_name = "penpot-edge";
        metrics_path = "/probe";
        params.module = [ "penpot_https" ];
        static_configs = [
          {
            targets = [ "https://${domain}/readyz" ];
            labels.service = "penpot";
          }
        ];
        relabel_configs = [
          {
            source_labels = [ "__address__" ];
            target_label = "__param_target";
          }
          {
            source_labels = [ "__param_target" ];
            target_label = "instance";
          }
          {
            target_label = "__address__";
            replacement = "127.0.0.1:9115";
          }
        ];
      }
    ];
    # A standalone rule file: the NixOS module writes it as its own
    # `rule_files` entry, so there is no indentation coupling with the
    # concatenated `rules` document.
    services.prometheus.ruleFiles = lib.mkAfter [
      (pkgs.writeText "penpot-prometheus.rules" ''
        groups:
          - name: penpot
            rules:
              - alert: PenpotServiceUnavailable
                expr: probe_success{job="penpot-edge"} != 1 or absent(probe_success{job="penpot-edge"})
                for: 5m
                labels:
                  severity: critical
                  service: penpot
                annotations:
                  summary: Penpot HTTPS/backend readiness probe failed
      '')
    ];
  };
}
