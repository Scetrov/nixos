{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.scetrov.services.forgejo.mirrors;
  policyType = lib.types.submodule {
    options = {
      owner = lib.mkOption { type = lib.types.str; };
      ownerId = lib.mkOption { type = lib.types.ints.positive; };
      pattern = lib.mkOption {
        type = lib.types.str;
        default = "*";
      };
      namespace = lib.mkOption { type = lib.types.str; };
      namespaceId = lib.mkOption {
        type = lib.types.nullOr lib.types.ints.positive;
        default = null;
        description = "Stable ID of an explicitly authorized private Forgejo organization.";
      };
      includePrivate = lib.mkOption {
        type = lib.types.bool;
        default = false;
      };
      includeForks = lib.mkOption {
        type = lib.types.bool;
        default = false;
      };
      includeArchived = lib.mkOption {
        type = lib.types.bool;
        default = false;
      };
    };
  };
  policy = pkgs.writeText "forgejo-mirrors.json" (
    builtins.toJSON {
      inherit (cfg)
        policies
        reportOnly
        mirrorInterval
        staleAfterSeconds
        lfsVerified
        privateAuthVerified
        ;
    }
  );
in
{
  options.scetrov.services.forgejo.mirrors = {
    enable = lib.mkEnableOption "outbound GitHub discovery and private Forgejo pull mirrors";
    reportOnly = lib.mkOption {
      type = lib.types.bool;
      default = true;
    };
    importApproved = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Operator approved inventory, capacity, eligibility and namespace ownership.";
    };
    lfsVerified = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Installed native LFS import/polling and failure detection were verified; required before imports.";
    };
    privateAuthVerified = lib.mkOption {
      type = lib.types.bool;
      default = false;
    };
    githubCredential = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Load optional vault-backed GitHub token; public-only discovery needs none.";
    };
    interval = lib.mkOption {
      type = lib.types.str;
      default = "hourly";
    };
    mirrorInterval = lib.mkOption {
      type = lib.types.str;
      default = "1h";
    };
    staleAfterSeconds = lib.mkOption {
      type = lib.types.ints.positive;
      default = 10800;
    };
    policies = lib.mkOption {
      type = lib.types.listOf policyType;
      default = [
        {
          owner = "Scetrov";
          ownerId = 144595937;
          namespace = "gh-Scetrov";
        }
        {
          owner = "RichardSlater";
          ownerId = 630786;
          namespace = "gh-RichardSlater";
        }
        {
          owner = "storytold";
          ownerId = 76897702;
          pattern = "*craft";
          namespace = "gh-storytold";
        }
      ];
    };
  };

  config = lib.mkIf cfg.enable {
    # Native import AND later mirror polling need the LFS server enabled.
    # Use the upstream module to provision persistent storage and its JWT secret.
    # This does not attest completeness: lfsVerified remains a separate gate.
    services.forgejo.lfs.enable = true;

    assertions = [
      {
        assertion = config.scetrov.services.forgejo.enable && config.networking.hostName == "habiki";
        message = "Forgejo mirrors require the private Habiki Forgejo service.";
      }
      {
        assertion =
          cfg.policies != [ ]
          && lib.length (lib.unique (map (p: p.ownerId) cfg.policies)) == lib.length cfg.policies;
        message = "Mirror policy requires unique stable source owner IDs.";
      }
      {
        assertion =
          lib.length (lib.unique (map (p: lib.toLower p.namespace) cfg.policies)) == lib.length cfg.policies;
        message = "Mirror namespaces must not collide.";
      }
      {
        assertion = lib.all (
          p:
          builtins.match "[A-Za-z0-9][A-Za-z0-9_.-]*" p.owner != null
          && builtins.match "[A-Za-z0-9][A-Za-z0-9_.-]*" p.namespace != null
        ) cfg.policies;
        message = "Mirror owner and namespace identifiers must be safe API path components.";
      }
      {
        assertion =
          cfg.reportOnly
          || (cfg.importApproved && cfg.lfsVerified && lib.all (p: p.namespaceId != null) cfg.policies);
        message = "Imports require approved inventory, authorized namespace IDs and verified native LFS behavior.";
      }
      {
        assertion = lib.all (
          p: !p.includePrivate || (cfg.githubCredential && cfg.privateAuthVerified)
        ) cfg.policies;
        message = "Private sources require dedicated credentials and verified private-source authorization.";
      }
      {
        assertion = config.services.forgejo.settings.repository.FORCE_PRIVATE;
        message = "Mirror destinations require FORCE_PRIVATE.";
      }
    ];
    age.secrets.forgejo_mirrors_token = {
      file = /root/secrets/forgejo_mirrors_token.age;
      mode = "0400";
    };
    age.secrets.forgejo_mirrors_github_token = lib.mkIf cfg.githubCredential {
      file = /root/secrets/forgejo_mirrors_github_token.age;
      mode = "0400";
    };
    users.groups.forgejo-mirrors = { };
    users.users.forgejo-mirrors = {
      isSystemUser = true;
      group = "forgejo-mirrors";
    };
    systemd.tmpfiles.rules = [ "d /var/lib/forgejo-mirrors-metrics 2750 forgejo-mirrors alloy -" ];
    systemd.services.forgejo-mirrors = {
      description = "Discover GitHub sources and reconcile private native Forgejo mirrors";
      wants = [
        "network-online.target"
        "forgejo.service"
      ];
      after = [
        "network-online.target"
        "forgejo.service"
      ];
      unitConfig = {
        StartLimitIntervalSec = 3600;
        StartLimitBurst = 3;
      };
      restartTriggers = [
        config.age.secrets.forgejo_mirrors_token.file
      ]
      ++ lib.optional cfg.githubCredential config.age.secrets.forgejo_mirrors_github_token.file;
      serviceConfig = {
        Type = "oneshot";
        User = "forgejo-mirrors";
        Group = "forgejo-mirrors";
        StateDirectory = "forgejo-mirrors";
        StateDirectoryMode = "0700";
        UMask = "0077";
        LoadCredential = [
          "forgejo:${config.age.secrets.forgejo_mirrors_token.path}"
        ]
        ++ lib.optional cfg.githubCredential "github:${config.age.secrets.forgejo_mirrors_github_token.path}";
        ExecStart = "${lib.getExe pkgs.python3} ${./forgejo-mirrors.py} --config ${policy} --state-dir /var/lib/forgejo-mirrors --metrics-file /var/lib/forgejo-mirrors-metrics/mirrors.prom";
        ReadWritePaths = [ "/var/lib/forgejo-mirrors-metrics" ];
        Restart = "on-failure";
        RestartSec = 30;
        TimeoutStartSec = "45min";
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
        LimitFSIZE = "64M";
      };
    };
    systemd.timers.forgejo-mirrors = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = cfg.interval;
        Persistent = true;
        RandomizedDelaySec = 60;
      };
    };
  };
}
