{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.scetrov.services.github-repository-observability;
  exporter = pkgs.writeShellApplication {
    name = "github-repository-observability-exporter";
    runtimeInputs = [ (pkgs.python3.withPackages (ps: [ ps.cryptography ])) ];
    text = ''
      exec python3 ${../pkgs/github-repository-observability-exporter.py} "$@"
    '';
  };
in
{
  options.scetrov.services.github-repository-observability = {
    enable = lib.mkEnableOption "GitHub repository observability exporter";

    owners = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [
        "Scetrov"
        "RichardSlater"
      ];
      description = "GitHub owners whose repositories are collected when visible to the GitHub App installation.";
    };

    includeArchived = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Whether archived repositories are included in emitted repository risk metrics.";
    };

    includeForks = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Whether fork repositories are included in emitted repository risk metrics.";
    };

    excludeRepositories = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      example = [ "Scetrov/noisy-archive" ];
      description = "Full owner/repository names to suppress from repository risk metrics.";
    };

    collectionIntervalSeconds = lib.mkOption {
      type = lib.types.ints.positive;
      default = 900;
      description = "Background GitHub collection interval, independent from Prometheus scrape cadence.";
    };

    listenAddress = lib.mkOption {
      type = lib.types.str;
      default = "127.0.0.1:9177";
      description = "Exporter metrics listen address in host:port form.";
    };

    githubAppIdFile = lib.mkOption {
      type = lib.types.path;
      default = config.age.secrets.github_repository_observability_app_id.path;
      description = "Runtime secret file containing the numeric GitHub App ID.";
    };

    githubPrivateKeyFile = lib.mkOption {
      type = lib.types.path;
      default = config.age.secrets.github_repository_observability_private_key.path;
      description = "Runtime secret file containing the GitHub App PEM private key.";
    };
  };

  config = lib.mkIf cfg.enable {
    age.secrets.github_repository_observability_app_id = {
      file = /root/secrets/github_repository_observability_app_id.age;
      owner = "github-repository-observability";
      group = "github-repository-observability";
      mode = "0400";
    };

    age.secrets.github_repository_observability_private_key = {
      file = /root/secrets/github_repository_observability_private_key.age;
      owner = "github-repository-observability";
      group = "github-repository-observability";
      mode = "0400";
    };

    users.users.github-repository-observability = {
      isSystemUser = true;
      group = "github-repository-observability";
      description = "GitHub repository observability exporter";
    };
    users.groups.github-repository-observability = { };

    systemd.services.github-repository-observability = {
      description = "GitHub Repository Observability Exporter";
      wantedBy = [ "multi-user.target" ];
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
      serviceConfig = {
        Type = "simple";
        User = "github-repository-observability";
        Group = "github-repository-observability";
        DynamicUser = false;
        Restart = "on-failure";
        RestartSec = "30s";
        NoNewPrivileges = true;
        PrivateTmp = true;
        ProtectHome = true;
        ProtectSystem = "strict";
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        LockPersonality = true;
        MemoryDenyWriteExecute = true;
        RestrictRealtime = true;
        SystemCallArchitectures = "native";
      };
      script = ''
        exec ${exporter}/bin/github-repository-observability-exporter \
          --github-app-id-file ${lib.escapeShellArg cfg.githubAppIdFile} \
          --github-private-key-file ${lib.escapeShellArg cfg.githubPrivateKeyFile} \
          ${
            lib.concatMapStringsSep " \\\n          " (owner: "--owner ${lib.escapeShellArg owner}") cfg.owners
          } \
          ${lib.optionalString cfg.includeArchived "--include-archived \\\n          "}${lib.optionalString cfg.includeForks "--include-forks \\\n          "}${
            lib.concatMapStringsSep " \\\n          " (
              repo: "--exclude-repository ${lib.escapeShellArg repo}"
            ) cfg.excludeRepositories
          } \
          --collection-interval-seconds ${toString cfg.collectionIntervalSeconds} \
          --listen-address ${lib.escapeShellArg cfg.listenAddress}
      '';
    };
  };
}
