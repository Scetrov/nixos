{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.scetrov.services.ai-usage;
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

    codexSecretFile = lib.mkOption {
      type = lib.types.path;
      default = config.age.secrets.codex_oauth.path;
      description = "Runtime secret file containing the Codex OAuth JSON credential (access, refresh, expires, accountId).";
    };

    openrouterEnvFile = lib.mkOption {
      type = lib.types.path;
      default = config.age.secrets.openrouter_management_env.path;
      description = "Runtime environment file containing OPENROUTER_API_KEY for OpenRouter credits polling.";
    };
  };

  config = lib.mkIf cfg.enable {
    age.secrets.codex_oauth = {
      file = /root/secrets/codex_oauth_env.age;
      owner = "ai-usage-exporter";
      group = "ai-usage-exporter";
      mode = "0400";
    };

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

    systemd.services.ai-usage-exporter = {
      description = "AI Usage Metrics Exporter (Codex + OpenRouter)";
      wantedBy = [ "multi-user.target" ];
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
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
          --codex-secret-file ${lib.escapeShellArg cfg.codexSecretFile} \
          --openrouter-env-file ${lib.escapeShellArg cfg.openrouterEnvFile} \
          --listen-address ${lib.escapeShellArg cfg.listenAddress} \
          --poll-interval ${toString cfg.pollInterval}
      '';
    };
  };
}
