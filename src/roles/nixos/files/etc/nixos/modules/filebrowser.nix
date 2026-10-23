{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.scetrov.services.filebrowser;
  enrollments = builtins.fromJSON (builtins.readFile cfg.enrollmentsFile);
  usernames = map (entry: entry.unix_username) enrollments;
  serviceId = 61990;
  runtimeDir = "/run/filebrowser";
in
{
  options.scetrov.services.filebrowser = {
    enable = lib.mkEnableOption "private shared FileBrowser Quantum Documents service";
    port = lib.mkOption {
      type = lib.types.port;
      default = 8092;
    };
    enrollmentsFile = lib.mkOption {
      type = lib.types.path;
      default = ./filebrowser-enrollments.json;
      internal = true;
    };
    toolDirectory = lib.mkOption {
      type = lib.types.path;
      default = ./.;
      internal = true;
    };
  };

  config = lib.mkMerge [
    (lib.mkIf config.services.grafana.enable {
      services.grafana.provision.alerting.rules.settings = {
        apiVersion = 1;
        deleteRules = lib.optional (!cfg.enable) {
          orgId = 1;
          uid = "filebrowser-unavailable";
        };
        groups = lib.optional cfg.enable {
          orgId = 1;
          name = "Filebrowser availability";
          folder = "Operations / Services";
          interval = "60s";
          rules = [
            {
              uid = "filebrowser-unavailable";
              title = "FilebrowserServiceUnavailable";
              condition = "B";
              for = "5m";
              noDataState = "Alerting";
              execErrState = "Alerting";
              labels = {
                severity = "critical";
                service = "filebrowser";
                host = "habiki";
              };
              annotations = {
                summary = "Filebrowser HTTPS health/readiness has failed for five minutes";
                description = "Check podman-filebrowser.service, filebrowser-reconcile.service and /run/filebrowser/ready. See docs/filebrowser.md. Do not bypass the readiness gate.";
              };
              data = [
                {
                  refId = "A";
                  datasourceUid = "mimir";
                  relativeTimeRange = {
                    from = 600;
                    to = 0;
                  };
                  model = {
                    refId = "A";
                    expr = ''probe_success{job="filebrowser-edge",service="filebrowser"} == bool 0 or absent(probe_success{job="filebrowser-edge",service="filebrowser"})'';
                    instant = true;
                    range = false;
                    intervalMs = 1000;
                    maxDataPoints = 43200;
                  };
                }
                {
                  refId = "B";
                  datasourceUid = "__expr__";
                  relativeTimeRange = {
                    from = 0;
                    to = 0;
                  };
                  model = {
                    refId = "B";
                    type = "math";
                    expression = "$A > 0";
                  };
                }
              ];
            }
          ];
        };
      };
    })
    (lib.mkIf cfg.enable {
      assertions = [
        {
          assertion = pkgs.stdenv.hostPlatform.system == "x86_64-linux";
          message = "The reviewed Filebrowser image pin is Linux amd64 only.";
        }
        {
          assertion =
            builtins.length usernames == builtins.length (lib.unique usernames)
            && lib.all (name: builtins.match "[a-z_][a-z0-9_-]{0,31}" name != null) usernames;
          message = "Filebrowser mount slots require unique exact lowercase Unix usernames.";
        }
      ];

      users.groups.filebrowser.gid = serviceId;
      users.users.filebrowser = {
        isSystemUser = true;
        uid = serviceId;
        group = "filebrowser";
        home = "/var/lib/filebrowser";
        shell = "${pkgs.shadow}/bin/nologin";
      };
      age.secrets = {
        filebrowser_reconciler_public_key = {
          file = /root/secrets/filebrowser_reconciler_public_key.age;
          mode = "0400";
        };
        filebrowser_reconciler_client_id = {
          file = /root/secrets/filebrowser_reconciler_client_id.age;
          mode = "0400";
        };
        filebrowser_reconciler_app_password = {
          file = /root/secrets/filebrowser_reconciler_app_password.age;
          mode = "0400";
        };
        filebrowser_oidc_client_id = {
          file = /root/secrets/filebrowser_oidc_client_id.age;
          mode = "0400";
        };
        filebrowser_oidc_client_secret = {
          file = /root/secrets/filebrowser_oidc_client_secret.age;
          mode = "0400";
        };
      };
      systemd.tmpfiles.rules = [
        "d /var/lib/filebrowser 0700 filebrowser filebrowser -"
        "d /var/lib/filebrowser-enrollment 0700 root root -"
        "d ${runtimeDir} 0755 root root -"
      ];

      virtualisation.oci-containers = {
        backend = "podman";
        containers.filebrowser = {
          image = "ghcr.io/gtsteffaniak/filebrowser@sha256:989e2dc6c491bda3c8bb82b27cd7798924ff3025cabdcad2444eb42f774836f6";
          user = "${toString serviceId}:${toString serviceId}";
          ports = [ "127.0.0.1:${toString cfg.port}:8080" ];
          cmd = [
            "-c"
            "/runtime/config.yaml"
          ];
          volumes = [
            "/var/lib/filebrowser:/state:rw"
            "${runtimeDir}/config.yaml:/runtime/config.yaml:ro"
          ]
          ++ map (name: "${runtimeDir}/mounts/${name}:/documents/${name}:rw") usernames;
          extraOptions = [
            "--userns=host"
            "--cap-drop=ALL"
            "--security-opt=no-new-privileges"
            "--read-only"
            "--tmpfs=/tmp:rw,noexec,nosuid,size=64m"
          ];
        };
      };
      services.caddy = {
        enable = true;
        virtualHosts."files.net.scetrov.live" = {
          useACMEHost = "scetrov.live";
          extraConfig = ''
            encode zstd gzip
            # /public/static contains the ordinary UI assets, not public shares.
            @publicAccess path /public/share* /public/api*
            handle @publicAccess {
              respond 404
            }
            handle /dav* {
              respond 404
            }
            @ready file {
              root /run/filebrowser
              try_files ready
            }
            handle @ready {
              reverse_proxy 127.0.0.1:${toString cfg.port} {
                header_up -X-Filebrowser-Admin-Assertion
              }
            }
            handle {
              respond "File service is awaiting verified scope reconciliation" 503
            }
          '';
        };
      };

      services.prometheus.scrapeConfigs = lib.mkIf config.services.prometheus.enable [
        {
          job_name = "filebrowser-edge";
          metrics_path = "/probe";
          params.module = [ "filebrowser_https" ];
          static_configs = [
            {
              targets = [ "https://127.0.0.1/health" ];
              labels.service = "filebrowser";
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
              replacement = "127.0.0.1:${toString config.services.prometheus.exporters.blackbox.port}";
            }
          ];
        }
      ];

      systemd.services.filebrowser-reconcile = {
        description = "Verify private Quantum Documents scopes before publishing readiness";
        after = [ "podman-filebrowser.service" ];
        requires = [ "podman-filebrowser.service" ];
        partOf = [ "podman-filebrowser.service" ];
        serviceConfig = {
          Type = "oneshot";
          ExecStart = "${pkgs.python3}/bin/python3 ${cfg.toolDirectory}/filebrowser_reconcile.py --enrollments ${cfg.enrollmentsFile} --port ${toString cfg.port}";
          LoadCredential = [
            "client-id:${config.age.secrets.filebrowser_reconciler_client_id.path}"
            "app-password:${config.age.secrets.filebrowser_reconciler_app_password.path}"
          ];
          TimeoutStartSec = 180;
          UMask = "0077";
          NoNewPrivileges = true;
          PrivateTmp = true;
          PrivateDevices = true;
          ProtectSystem = "strict";
          ProtectHome = true;
          ProtectKernelTunables = true;
          ProtectKernelModules = true;
          ProtectControlGroups = true;
          RestrictSUIDSGID = true;
          LockPersonality = true;
          CapabilityBoundingSet = "";
          RestrictAddressFamilies = [
            "AF_INET"
            "AF_UNIX"
          ];
          ReadWritePaths = [ runtimeDir ];
          StandardOutput = "journal";
          StandardError = "journal";
        };
      };
      systemd.services.podman-filebrowser = {
        wants = [ "filebrowser-reconcile.service" ];
        path = [
          pkgs.acl
          pkgs.shadow
          pkgs.util-linux
        ];
        preStart = lib.mkBefore ''
          ${pkgs.python3}/bin/python3 ${cfg.toolDirectory}/filebrowser_runtime.py \
            --enrollments ${cfg.enrollmentsFile} --port ${toString cfg.port}
        '';
        postStop = ''
          rm -f ${runtimeDir}/ready
        '';
        restartTriggers = [
          cfg.enrollmentsFile
          config.age.secrets.filebrowser_oidc_client_id.file
          config.age.secrets.filebrowser_oidc_client_secret.file
          config.age.secrets.filebrowser_reconciler_public_key.file
        ];
        serviceConfig = {
          UMask = "0077";
          LoadCredential = [
            "machine-public-key:${config.age.secrets.filebrowser_reconciler_public_key.path}"
            "oidc-client-id:${config.age.secrets.filebrowser_oidc_client_id.path}"
            "oidc-client-secret:${config.age.secrets.filebrowser_oidc_client_secret.path}"
          ];
          StandardOutput = "journal";
          StandardError = "journal";
        };
      };
    })
  ];
}
