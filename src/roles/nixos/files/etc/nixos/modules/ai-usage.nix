{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.scetrov.services.ai-usage;
  codexAppServerImage = import ../pkgs/codex-app-server-image.nix { inherit pkgs; };
  codexAppServerStaleSocketCleanup = pkgs.writeShellApplication {
    name = "codex-app-server-stale-socket-cleanup";
    runtimeInputs = [
      pkgs.coreutils
      pkgs.podman
      pkgs.psmisc
    ];
    text = ''
      set -euo pipefail
      socket=${lib.escapeShellArg cfg.codexAppServer.socketPath}
      runtime_directory=${lib.escapeShellArg cfg.codexAppServer.runtimeDirectory}

      chgrp ai-usage-exporter "$runtime_directory"
      chmod 2770 "$runtime_directory"

      if [ ! -e "$socket" ]; then
        exit 0
      fi
      if [ ! -S "$socket" ]; then
        echo "Refusing to remove non-socket path: $socket" >&2
        exit 1
      fi
      if podman container inspect codex-app-server-runtime >/dev/null 2>&1 \
        && [ "$(podman container inspect codex-app-server-runtime --format '{{.State.Running}}')" = true ]; then
        echo "Refusing to remove socket while the managed container is running" >&2
        exit 1
      fi
      if fuser "$socket" >/dev/null 2>&1; then
        echo "Refusing to remove socket owned by an active process" >&2
        exit 1
      fi
      rm -- "$socket"
    '';
  };
  codexAppServerReadiness = pkgs.writeShellApplication {
    name = "codex-app-server-readiness";
    runtimeInputs = [
      pkgs.coreutils
      pkgs.python3
    ];
    text = ''
      set -euo pipefail
      socket=${lib.escapeShellArg cfg.codexAppServer.socketPath}

      python3 ${../pkgs/codex-app-server-readiness.py} \
        --socket "$socket" \
        --timeout 10
      chgrp ai-usage-exporter ${lib.escapeShellArg cfg.codexAppServer.runtimeDirectory}
      chmod 2770 ${lib.escapeShellArg cfg.codexAppServer.runtimeDirectory}
      chgrp ai-usage-exporter "$socket"
      chmod 0660 "$socket"
      test "$(stat -c %U "$socket")" = codex-app-server
      test "$(stat -c %G "$socket")" = ai-usage-exporter
      test "$(stat -c %a "$socket")" = 660
    '';
  };
  codexAppServerEnroll = pkgs.writeShellApplication {
    name = "codex-app-server-enroll";
    runtimeInputs = [
      pkgs.coreutils
      pkgs.podman
      pkgs.systemd
      pkgs.util-linux
    ];
    text = ''
      set -euo pipefail

      if [ "$(id -u)" -ne 0 ]; then
        echo "codex-app-server-enroll must run through sudo" >&2
        exit 1
      fi

      cd /tmp
      systemctl stop podman-codex-app-server-runtime.service
      if ! runuser -u codex-app-server -- \
        env HOME=/var/lib/codex-app-server-podman XDG_RUNTIME_DIR=/run/user/979 \
        podman run --rm -it \
          --log-driver=none \
          --read-only \
          --network=podman \
          --cap-drop=ALL \
          --security-opt=no-new-privileges \
          --userns=keep-id:uid=10001,gid=10001 \
          --user=10001:10001 \
          --tmpfs=/tmp:rw,noexec,nosuid,nodev,size=16m \
          -v ${lib.escapeShellArg cfg.codexAppServer.stateDirectory}:/var/lib/codex-app-server:rw \
          --entrypoint=/bin/codex \
          ${lib.escapeShellArg cfg.codexAppServer.image} login --device-auth; then
        echo "Enrollment failed; app-server remains stopped" >&2
        exit 1
      fi

      systemctl start podman-codex-app-server-runtime.service
      systemctl is-active --quiet podman-codex-app-server-runtime.service
      echo "Codex app-server enrollment and readiness succeeded"
    '';
  };
  exporter = pkgs.writeShellApplication {
    name = "ai-usage-exporter";
    runtimeInputs = [ pkgs.python3 ];
    text = ''
      exec python3 ${../pkgs/ai-usage-exporter.py} "$@"
    '';
  };
in
{
  options.scetrov.services.ai-usage = {
    enable = lib.mkEnableOption "AI usage metrics exporter for Codex and OpenRouter";

    listenAddress = lib.mkOption {
      type = lib.types.str;
      default = "127.0.0.1:9188";
      description = "Exporter metrics listen address in host:port form.";
    };

    pollInterval = lib.mkOption {
      type = lib.types.ints.positive;
      default = 900;
      description = "Polling interval in seconds for Codex and OpenRouter APIs.";
    };

    codexAppServer = {
      enable = lib.mkEnableOption "the local Codex app-server runtime";

      image = lib.mkOption {
        type = lib.types.str;
        default = "codex-app-server:0.145.0";
        readOnly = true;
        description = "Immutable local image name for the pinned Codex app-server build.";
      };

      imageFile = lib.mkOption {
        type = lib.types.path;
        default = codexAppServerImage;
        readOnly = true;
        description = "Nix-built OCI archive loaded into Podman without a registry pull.";
      };

      stateDirectory = lib.mkOption {
        type = lib.types.str;
        default = "/var/lib/codex-app-server";
        description = "Protected persistent CODEX_HOME directory.";
      };

      runtimeDirectory = lib.mkOption {
        type = lib.types.str;
        default = "/run/codex-app-server";
        description = "Runtime directory containing the local control socket.";
      };

      socketPath = lib.mkOption {
        type = lib.types.str;
        default = "${cfg.codexAppServer.runtimeDirectory}/control.sock";
        readOnly = true;
        description = "Local Codex app-server Unix control socket.";
      };
    };

    openrouterEnvFile = lib.mkOption {
      type = lib.types.path;
      default = config.age.secrets.openrouter_management_env.path;
      description = "Runtime environment file containing OPENROUTER_API_KEY for OpenRouter credits polling.";
    };
  };

  config = lib.mkIf cfg.enable {
    age.secrets.openrouter_management_env = {
      file = /root/secrets/openrouter_management_env.age;
      owner = "ai-usage-exporter";
      group = "ai-usage-exporter";
      mode = "0400";
    };

    users.users.ai-usage-exporter = {
      isSystemUser = true;
      group = "ai-usage-exporter";
      description = "AI usage metrics exporter";
    };
    users.groups.ai-usage-exporter = { };

    users.groups.codex-app-server = lib.mkIf cfg.codexAppServer.enable {
      gid = 979;
    };
    users.users.codex-app-server = lib.mkIf cfg.codexAppServer.enable {
      isSystemUser = true;
      uid = 979;
      group = "codex-app-server";
      extraGroups = [ "ai-usage-exporter" ];
      description = "Rootless Codex app-server runtime";
      home = "/var/lib/codex-app-server-podman";
      createHome = true;
      shell = "${pkgs.shadow}/bin/nologin";
      linger = true;
      subUidRanges = [
        {
          startUid = 165536;
          count = 65536;
        }
      ];
      subGidRanges = [
        {
          startGid = 165536;
          count = 65536;
        }
      ];
    };

    environment.systemPackages = lib.optionals cfg.codexAppServer.enable [
      codexAppServerEnroll
    ];

    systemd.tmpfiles.rules = lib.optionals cfg.codexAppServer.enable [
      "d /var/lib/codex-app-server-podman 0700 codex-app-server codex-app-server - -"
      "d ${cfg.codexAppServer.stateDirectory} 0700 codex-app-server codex-app-server - -"
      "d ${cfg.codexAppServer.runtimeDirectory} 2770 codex-app-server ai-usage-exporter - -"
    ];

    virtualisation.oci-containers.containers.codex-app-server-runtime =
      lib.mkIf cfg.codexAppServer.enable
        {
          image = cfg.codexAppServer.image;
          imageFile = cfg.codexAppServer.imageFile;
          autoStart = true;
          pull = "never";
          log-driver = "journald";
          user = "10001:10001";
          networks = [ "podman" ];
          ports = [ ];
          volumes = [
            "${cfg.codexAppServer.stateDirectory}:/var/lib/codex-app-server:rw"
            "${cfg.codexAppServer.runtimeDirectory}:/run/codex-app-server:rw"
          ];
          extraOptions = [
            "--read-only"
            "--cap-drop=ALL"
            "--security-opt=no-new-privileges"
            "--userns=keep-id:uid=10001,gid=10001"
            "--group-add=keep-groups"
            "--pids-limit=128"
            "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=16m"
          ];
          podman = {
            user = "codex-app-server";
            sdnotify = "conmon";
          };
        };

    systemd.services.podman-codex-app-server-runtime = lib.mkIf cfg.codexAppServer.enable {
      serviceConfig = {
        ExecStartPre = lib.mkBefore [
          "${codexAppServerStaleSocketCleanup}/bin/codex-app-server-stale-socket-cleanup"
        ];
        ExecStartPost = [
          "${codexAppServerReadiness}/bin/codex-app-server-readiness"
        ];
        Restart = "on-failure";
        RestartSec = "5s";
        UMask = "0007";
      };
    };

    systemd.services.ai-usage-exporter = {
      description = "AI Usage Metrics Exporter (Codex + OpenRouter)";
      wantedBy = [ "multi-user.target" ];
      after = [
        "network-online.target"
      ]
      ++ lib.optional cfg.codexAppServer.enable "podman-codex-app-server-runtime.service";
      wants = [
        "network-online.target"
      ]
      ++ lib.optional cfg.codexAppServer.enable "podman-codex-app-server-runtime.service";
      serviceConfig = {
        Type = "simple";
        User = "ai-usage-exporter";
        Group = "ai-usage-exporter";
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
        exec ${exporter}/bin/ai-usage-exporter \
          --codex-socket ${lib.escapeShellArg cfg.codexAppServer.socketPath} \
          --openrouter-env-file ${lib.escapeShellArg cfg.openrouterEnvFile} \
          --listen-address ${lib.escapeShellArg cfg.listenAddress} \
          --poll-interval ${toString cfg.pollInterval}
      '';
    };
  };
}
