{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.scetrov.services.github-sbom-collector;
  python = pkgs.python3.withPackages (ps: [
    ps.jsonschema
    ps.cryptography
  ]);
  schemaCommit = "55343ba19dee1785acf1ce9191540d5fd7b590db";
  schemas = pkgs.linkFarm "cyclonedx-1.6-schemas" (
    lib.mapAttrsToList
      (name: hash: {
        inherit name;
        path = pkgs.fetchurl {
          url = "https://raw.githubusercontent.com/CycloneDX/specification/${schemaCommit}/schema/${name}";
          inherit hash;
        };
      })
      {
        "bom-1.6.schema.json" = "sha256-PpLd28MM9/agK4DwlCsaTP1PscJvHfxDEK+p1hPK+5M=";
        "spdx.schema.json" = "sha256-uqnTvR7Ve2dRsIh+3q1rUGP/U/90Kc+F1HbGyUrwFm4=";
        "jsf-0.82.schema.json" = "sha256-i64ALCXnI9t+4fJq/eaArhorGo9rS0sP1l3DvssJCq4=";
      }
  );
  collectorConfig = pkgs.writeText "github-sbom-collector.json" (
    builtins.toJSON {
      inherit (cfg) sources dtrackUrl;
      githubApp = {
        appId = cfg.githubAppId;
        installationIds = cfg.githubInstallationIds;
      };
    }
  );
  sourceType = lib.types.submodule {
    options = {
      repository = lib.mkOption {
        type = lib.types.str;
        description = "Approved owner/repository.";
      };
      repositoryId = lib.mkOption {
        type = lib.types.ints.positive;
        description = "Stable GitHub repository ID.";
      };
      workflowId = lib.mkOption {
        type = lib.types.ints.positive;
        description = "Approved workflow ID.";
      };
      event = lib.mkOption {
        type = lib.types.enum [ "push" ];
        default = "push";
      };
      branch = lib.mkOption {
        type = lib.types.str;
        default = "main";
      };
      artifact = lib.mkOption {
        type = lib.types.str;
        default = "cyclonedx-sbom-v1";
      };
      path = lib.mkOption {
        type = lib.types.str;
        default = "bom.json";
      };
      project = lib.mkOption {
        type = lib.types.str;
        description = "Pre-provisioned Dependency-Track project UUID; never payload-controlled.";
      };
      version = lib.mkOption {
        type = lib.types.str;
        default = "main";
        description = "Configured target version, used as checkpoint identity.";
      };
    };
  };
in
{
  options.scetrov.services.github-sbom-collector = {
    enable = lib.mkEnableOption "private outbound GitHub SBOM upload collector";
    sources = lib.mkOption {
      type = lib.types.listOf sourceType;
      default = [ ];
    };
    dtrackUrl = lib.mkOption {
      type = lib.types.str;
      default = "https://dtrack-api.net.scetrov.live";
    };
    reportOnly = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Discover eligible artifacts without downloading, uploading or changing checkpoints.";
    };
    interval = lib.mkOption {
      type = lib.types.str;
      default = "*:0/15";
    };
    githubAppId = lib.mkOption {
      type = lib.types.ints.unsigned;
      default = 0;
      description = "Public ID of the dedicated SBOM GitHub App (not the Grafana App).";
    };
    githubInstallationIds = lib.mkOption {
      type = lib.types.listOf lib.types.ints.positive;
      default = [ ];
      description = "Approved installation IDs for the dedicated App across accounts/organisations.";
    };
    githubPrivateKeyFile = lib.mkOption {
      type = lib.types.str;
      default = "/run/agenix/github_sbom_collector_private_key";
      description = "Protected runtime RSA PEM private key for the dedicated GitHub App.";
    };
    dtrackTokenFile = lib.mkOption {
      type = lib.types.str;
      default = "/run/agenix/dtrack_sbom_collector_token";
      description = "Protected runtime BOM_UPLOAD API key file.";
    };
  };

  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = cfg.sources != [ ];
        message = "SBOM collection requires explicit approved producer/target mappings.";
      }
      {
        assertion =
          cfg.githubAppId > 0
          && cfg.githubInstallationIds != [ ]
          && lib.unique cfg.githubInstallationIds == cfg.githubInstallationIds;
        message = "SBOM collection requires a dedicated GitHub App ID and a nonempty array of unique installation IDs.";
      }
      {
        assertion = lib.all (
          source:
          builtins.match "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}" source.project
          != null
        ) cfg.sources;
        message = "Each SBOM source must use a pre-created Dependency-Track project UUID.";
      }
    ];
    age.secrets.github_sbom_collector_private_key.file = /root/secrets/github_sbom_collector_private_key.age;
    age.secrets.dtrack_sbom_collector_token.file = /root/secrets/dtrack_sbom_collector_token.age;
    users.groups.github-sbom-collector = { };
    users.users.github-sbom-collector = {
      isSystemUser = true;
      group = "github-sbom-collector";
    };
    # Existing Alloy unix/textfile collector reads only the public metrics directory.
    systemd.tmpfiles.rules = [
      "d /var/lib/github-sbom-collector-metrics 2750 github-sbom-collector alloy -"
    ];
    systemd.services.github-sbom-collector = {
      description = "Upload trusted GitHub SBOM artifacts to private Dependency-Track";
      wants = [ "network-online.target" ];
      after = [ "network-online.target" ];
      serviceConfig = {
        Type = "oneshot";
        User = "github-sbom-collector";
        Group = "github-sbom-collector";
        StateDirectory = "github-sbom-collector";
        StateDirectoryMode = "0700";
        UMask = "0077";
        LoadCredential = [
          "github-app-key:${cfg.githubPrivateKeyFile}"
          "dtrack:${cfg.dtrackTokenFile}"
        ];
        ExecStart = "${python}/bin/python3 ${../pkgs/github-sbom-collector.py} --config ${collectorConfig} --schemas ${schemas} --state-dir /var/lib/github-sbom-collector --metrics-file /var/lib/github-sbom-collector-metrics/collector.prom${lib.optionalString cfg.reportOnly " --report-only"}";
        ReadWritePaths = [ "/var/lib/github-sbom-collector-metrics" ];
        NoNewPrivileges = true;
        PrivateTmp = true;
        PrivateDevices = true;
        ProtectHome = true;
        ProtectSystem = "strict";
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        RestrictSUIDSGID = true;
        RestrictRealtime = true;
        LockPersonality = true;
        MemoryDenyWriteExecute = true;
        RestrictAddressFamilies = [
          "AF_UNIX"
          "AF_INET"
          "AF_INET6"
        ];
        CapabilityBoundingSet = "";
        MemoryMax = "512M";
        TasksMax = 16;
        # RuntimeMaxSec has no effect on Type=oneshot; bound the whole invocation here.
        TimeoutStartSec = 300;
        LimitFSIZE = "64M";
      };
    };
    systemd.timers.github-sbom-collector = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = cfg.interval;
        Persistent = true;
        RandomizedDelaySec = 30;
      };
    };
  };
}
