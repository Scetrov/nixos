{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.services.hermes-webui;
  inherit (lib)
    mkEnableOption
    mkIf
    mkOption
    types
    ;

  backendPackage =
    if cfg.backend == "docker" then
      config.virtualisation.docker.package
    else
      config.virtualisation.podman.package;

  backendBin = "${backendPackage}/bin/${cfg.backend}";
  shellBin = "${pkgs.runtimeShell}";
  catBin = "${pkgs.coreutils}/bin/cat";
  chmodBin = "${pkgs.coreutils}/bin/chmod";
  chownBin = "${pkgs.coreutils}/bin/chown";
  installBin = "${pkgs.coreutils}/bin/install";
  mkdirBin = "${pkgs.coreutils}/bin/mkdir";
  setupUnit = "hermes-webui-oci-setup.service";
  containerUnit = name: "${cfg.backend}-${name}.service";
  optionalEnvFiles = lib.optional (cfg.environmentFile != null) cfg.environmentFile;
  rootlessPodman = cfg.rootless && cfg.backend == "podman";
  podmanRootlessConfig = lib.optionalAttrs rootlessPodman {
    podman = {
      user = cfg.user;
      sdnotify = "healthy";
    };
  };
  rootlessHealthOptions = lib.optionals rootlessPodman [
    "--health-cmd=true"
    "--health-interval=30s"
    "--health-start-period=2s"
  ];
  containerUid = cfg.uid;
  containerGid = cfg.gid;
  runtimeDir = "/run/user/${toString cfg.serviceUid}";
  caddyfile = pkgs.writeText "hermes-webui-Caddyfile" ''
    :80 {
      encode zstd gzip
      reverse_proxy hermes-webui:8787
    }
  '';
  webuiEnvFile = "${toString cfg.home}/webui.env";
  loadModelEnv = lib.optionalString (cfg.environmentFile != null) ''
    if [ -r ${lib.escapeShellArg cfg.environmentFile} ]; then
      while IFS='=' read -r key value; do
        case "$key" in
          ""|\#*) continue ;;
        esac
        if [ "$key" = ${lib.escapeShellArg cfg.defaultModelEnvVar} ]; then
          value="''${value%\"}"
          value="''${value#\"}"
          value="''${value%\'}"
          value="''${value#\'}"
          [ -n "$value" ] && default_model="$value"
        fi
      done < ${lib.escapeShellArg cfg.environmentFile}
    fi
  '';
in
{
  options.services.hermes-webui = {
    enable = mkEnableOption "Hermes WebUI multi-container stack";

    backend = mkOption {
      type = types.enum [
        "podman"
        "docker"
      ];
      default = "podman";
      description = "OCI backend used by virtualisation.oci-containers.";
    };

    rootless = mkOption {
      type = types.bool;
      default = true;
      description = "Run the Podman containers as the dedicated service user instead of root.";
    };

    user = mkOption {
      type = types.str;
      default = "hermes-webui";
      description = "Dedicated system user used for rootless Podman container services.";
    };

    group = mkOption {
      type = types.str;
      default = "hermes-webui";
      description = "Dedicated system group used for rootless Podman container services.";
    };

    serviceUid = mkOption {
      type = types.int;
      default = 992;
      description = "Static UID for the dedicated Hermes WebUI service user.";
    };

    serviceGid = mkOption {
      type = types.int;
      default = 992;
      description = "Static GID for the dedicated Hermes WebUI service group.";
    };

    home = mkOption {
      type = types.path;
      default = /var/lib/hermes-webui;
      description = "Home and persistent rootless Podman storage directory for the service user.";
    };

    allowRootlessPort80 = mkOption {
      type = types.bool;
      default = true;
      description = ''
        Lower net.ipv4.ip_unprivileged_port_start to 80 so rootless Caddy can bind host port 80.
        This is system-wide; disable it and use a higher caddyHostPort if you do not want that.
      '';
    };

    enableDashboard = mkOption {
      type = types.bool;
      default = true;
      description = "Run the Hermes dashboard container on dashboardPort.";
    };

    enableCaddy = mkOption {
      type = types.bool;
      default = true;
      description = "Run Caddy in front of Hermes WebUI and expose only HTTP port 80.";
    };

    caddyListenAddress = mkOption {
      type = types.str;
      default = "0.0.0.0";
      description = "Host address used for Caddy's published port 80.";
    };

    caddyHostPort = mkOption {
      type = types.port;
      default = 80;
      description = "Host port published by the Caddy reverse proxy.";
    };

    caddyImage = mkOption {
      type = types.str;
      default = "caddy:2-alpine";
      description = "Container image for the Caddy reverse proxy.";
    };

    gatewayPort = mkOption {
      type = types.port;
      default = 8642;
      description = "Host and container port for the Hermes gateway API.";
    };

    webuiPort = mkOption {
      type = types.port;
      default = 8787;
      description = "Host and container port for Hermes WebUI.";
    };

    dashboardPort = mkOption {
      type = types.port;
      default = 9119;
      description = "Host and container port for the Hermes dashboard.";
    };

    defaultModel = mkOption {
      type = types.str;
      default = "qwen/qwen3.6-flash";
      description = "Fallback Hermes model written to config.yaml when defaultModelEnvVar is unset.";
    };

    defaultModelEnvVar = mkOption {
      type = types.strMatching "[A-Za-z_][A-Za-z0-9_]*";
      default = "HERMES_DEFAULT_MODEL";
      description = "Environment variable read from environmentFile to set model.default in config.yaml.";
    };

    inferenceProvider = mkOption {
      type = types.str;
      default = "openrouter";
      description = "Hermes inference provider written to config.yaml.";
    };

    baseUrl = mkOption {
      type = types.str;
      default = "https://openrouter.ai/api/v1";
      description = "Provider base URL written to config.yaml.";
    };

    manageConfig = mkOption {
      type = types.bool;
      default = true;
      description = "Write non-secret Hermes model configuration into the hermes-home volume.";
    };

    uid = mkOption {
      type = types.int;
      default = 1000;
      description = "UID shared by the Hermes agent and WebUI containers.";
    };

    gid = mkOption {
      type = types.int;
      default = 1000;
      description = "GID shared by the Hermes agent and WebUI containers.";
    };

    workspace = mkOption {
      type = types.path;
      default = /var/lib/hermes-webui/workspace;
      description = "Host workspace bind-mounted at /workspace in Hermes WebUI.";
    };

    createWorkspace = mkOption {
      type = types.bool;
      default = true;
      description = "Create the host workspace directory with systemd-tmpfiles.";
    };

    networkName = mkOption {
      type = types.str;
      default = "hermes-net";
      description = "OCI network shared by the Hermes containers.";
    };

    homeVolume = mkOption {
      type = types.str;
      default = "hermes-home";
      description = "Named OCI volume for Hermes config, sessions, skills, and state.";
    };

    agentSourceVolume = mkOption {
      type = types.str;
      default = "hermes-agent-src";
      description = "Named OCI volume used to share the agent source with WebUI.";
    };

    agentImage = mkOption {
      type = types.str;
      default = "nousresearch/hermes-agent:latest";
      description = "Container image for the Hermes agent and dashboard.";
    };

    webuiImage = mkOption {
      type = types.str;
      default = "ghcr.io/nesquena/hermes-webui:latest";
      description = "Container image for Hermes WebUI.";
    };

    environmentFile = mkOption {
      type = types.nullOr types.path;
      default = null;
      example = "/run/secrets/hermes-webui.env";
      description = ''
        Optional root-owned env file passed to all Hermes containers.
        Keep API keys out of the Nix store by putting secrets here, for example:

        OPENROUTER_API_KEY=sk-or-v1-...
        HERMES_WEBUI_PASSWORD=change-me

        When rootless is enabled, this file must be readable by the service user.
        With sops-nix, set owner = config.services.hermes-webui.user.
      '';
    };

    extraEnvironment = mkOption {
      type = types.attrsOf types.str;
      default = { };
      description = "Additional non-secret environment variables added to all Hermes containers.";
    };
  };

  config = mkIf cfg.enable {
    assertions = [
      {
        assertion = !cfg.rootless || cfg.backend == "podman";
        message = "services.hermes-webui.rootless requires services.hermes-webui.backend = \"podman\".";
      }
      {
        assertion =
          !(rootlessPodman && cfg.enableCaddy && cfg.caddyHostPort < 1024) || cfg.allowRootlessPort80;
        message = ''
          Rootless Caddy cannot bind a privileged port without lowering net.ipv4.ip_unprivileged_port_start.
          Either keep allowRootlessPort80 enabled or set caddyHostPort to 1024 or higher.
        '';
      }
    ]
    ++ lib.optional (cfg.enableCaddy && cfg.environmentFile == null) {
      assertion = cfg.caddyListenAddress == "127.0.0.1";
      message = ''
        services.hermes-webui.caddyListenAddress is not localhost, but no environmentFile is set.
        Add a secret env file containing HERMES_WEBUI_PASSWORD before exposing Hermes WebUI remotely.
      '';
    };

    users.groups.${cfg.group}.gid = lib.mkIf rootlessPodman cfg.serviceGid;

    users.users.${cfg.user} = lib.mkIf rootlessPodman {
      isSystemUser = true;
      uid = cfg.serviceUid;
      group = cfg.group;
      home = toString cfg.home;
      createHome = true;
      shell = "${pkgs.shadow}/bin/nologin";
      linger = true;
      extraGroups = [ ];
      subUidRanges = [
        {
          startUid = 100000;
          count = 65536;
        }
      ];
      subGidRanges = [
        {
          startGid = 100000;
          count = 65536;
        }
      ];
    };

    # Sysctl net.ipv4.ip_unprivileged_port_start is already set to 0 in podman.nix,
    # which allows rootless Caddy to bind port 80 without further configuration.

    virtualisation.oci-containers.backend = cfg.backend;

    virtualisation.podman = mkIf (cfg.backend == "podman") {
      enable = true;
      dockerCompat = true;
      defaultNetwork.settings.dns_enabled = true;
    };

    virtualisation.docker.enable = mkIf (cfg.backend == "docker") true;

    systemd.tmpfiles.rules =
      lib.optionals rootlessPodman [
        "d ${toString cfg.home} 0750 ${cfg.user} ${cfg.group} - -"
        "Z ${toString cfg.home} 0750 ${cfg.user} ${cfg.group} - -"
      ]
      ++ lib.optional cfg.createWorkspace "d ${toString cfg.workspace} 0750 ${
        if rootlessPodman then cfg.user else toString cfg.uid
      } ${if rootlessPodman then cfg.group else toString cfg.gid} - -"
      ++ lib.optional (
        cfg.createWorkspace && rootlessPodman
      ) "Z ${toString cfg.workspace} 0750 ${cfg.user} ${cfg.group} - -";

    systemd.services.hermes-webui-oci-setup = {
      description = "Create Hermes WebUI OCI network and volumes";
      after =
        lib.optional (cfg.backend == "docker") "docker.service"
        ++ lib.optionals rootlessPodman [
          "linger-users.service"
          "user@${toString cfg.serviceUid}.service"
        ];
      requires =
        lib.optional (cfg.backend == "docker") "docker.service"
        ++ lib.optional rootlessPodman "user@${toString cfg.serviceUid}.service";
      wants = lib.optional rootlessPodman "linger-users.service";
      wantedBy = [
        (containerUnit "hermes-agent")
        (containerUnit "hermes-webui")
      ]
      ++ lib.optional cfg.enableDashboard (containerUnit "hermes-dashboard")
      ++ lib.optional cfg.enableCaddy (containerUnit "hermes-caddy");
      before = [
        (containerUnit "hermes-agent")
        (containerUnit "hermes-webui")
      ]
      ++ lib.optional cfg.enableDashboard (containerUnit "hermes-dashboard")
      ++ lib.optional cfg.enableCaddy (containerUnit "hermes-caddy");
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
      }
      // lib.optionalAttrs rootlessPodman {
        User = cfg.user;
        Group = cfg.group;
        RuntimeDirectory = "hermes-webui-setup";
      };
      environment = lib.optionalAttrs rootlessPodman {
        HOME = toString cfg.home;
        XDG_RUNTIME_DIR = runtimeDir;
      };
      path = [ backendPackage ];
      script = ''
        ${backendBin} network inspect ${lib.escapeShellArg cfg.networkName} >/dev/null 2>&1 \
        || ${backendBin} network create ${lib.escapeShellArg cfg.networkName}

        ${backendBin} volume inspect ${lib.escapeShellArg cfg.homeVolume} >/dev/null 2>&1 \
        || ${backendBin} volume create ${lib.escapeShellArg cfg.homeVolume}

        ${backendBin} volume inspect ${lib.escapeShellArg cfg.agentSourceVolume} >/dev/null 2>&1 \
        || ${backendBin} volume create ${lib.escapeShellArg cfg.agentSourceVolume}

        if [ "${if cfg.manageConfig then "1" else "0"}" = "1" ]; then
          default_model=${lib.escapeShellArg cfg.defaultModel}
          ${loadModelEnv}

          case "$default_model" in
            *[!A-Za-z0-9._:/+-]*)
              echo "Invalid Hermes model id in ${cfg.defaultModelEnvVar}: $default_model" >&2
              exit 1
              ;;
          esac

          home_mount="$(${backendBin} volume inspect ${lib.escapeShellArg cfg.homeVolume} --format '{{ .Mountpoint }}')"
          ${backendBin} unshare ${shellBin} -c '
            home_mount="$1"
            default_model="$2"
            provider="$3"
            base_url="$4"
            [ -d "$home_mount" ] || ${mkdirBin} -p "$home_mount"
            ${catBin} > "$home_mount/config.yaml" <<EOF
        model:
          default: "$default_model"
          provider: $provider
          base_url: $base_url
        EOF
            ${chownBin} ${toString containerUid}:${toString containerGid} "$home_mount/config.yaml"
            ${chmodBin} 0640 "$home_mount/config.yaml"
            ${catBin} > ${lib.escapeShellArg webuiEnvFile} <<EOF
        HERMES_WEBUI_DEFAULT_MODEL="$default_model"
        EOF
            ${chmodBin} 0644 ${lib.escapeShellArg webuiEnvFile}
          ' -- "$home_mount" "$default_model" ${lib.escapeShellArg cfg.inferenceProvider} ${lib.escapeShellArg cfg.baseUrl}

          ${lib.optionalString (cfg.environmentFile != null) ''
            if [ -r ${lib.escapeShellArg cfg.environmentFile} ]; then
              ${backendBin} unshare ${installBin} -o ${toString containerUid} -g ${toString containerGid} -m0600 ${lib.escapeShellArg cfg.environmentFile} "$home_mount/.env"
            fi
          ''}
        fi
      '';
    };

    virtualisation.oci-containers.containers = {
      hermes-agent = {
        image = cfg.agentImage;
        cmd = [
          "gateway"
          "run"
        ];
        volumes = [
          "${cfg.homeVolume}:/home/hermes/.hermes"
          "${cfg.agentSourceVolume}:/opt/hermes"
        ];
        environment = cfg.extraEnvironment // {
          HERMES_HOME = "/home/hermes/.hermes";
          HERMES_UID = toString containerUid;
          HERMES_GID = toString containerGid;
        };
        environmentFiles = optionalEnvFiles;
        extraOptions = [ "--network=${cfg.networkName}" ] ++ rootlessHealthOptions;
      }
      // podmanRootlessConfig;

      hermes-webui = {
        image = cfg.webuiImage;
        dependsOn = [ "hermes-agent" ];
        ports = lib.optional (!cfg.enableCaddy) "${cfg.caddyListenAddress}:${toString cfg.webuiPort}:8787";
        volumes = [
          "${cfg.homeVolume}:/home/hermeswebui/.hermes"
          "${cfg.agentSourceVolume}:/home/hermeswebui/.hermes/hermes-agent"
          "${toString cfg.workspace}:/workspace"
        ];
        environment = cfg.extraEnvironment // {
          HERMES_WEBUI_HOST = "0.0.0.0";
          HERMES_WEBUI_PORT = "8787";
          HERMES_WEBUI_STATE_DIR = "/home/hermeswebui/.hermes/webui";
          WANTED_UID = toString containerUid;
          WANTED_GID = toString containerGid;
        };
        environmentFiles = optionalEnvFiles ++ [ webuiEnvFile ];
        extraOptions = [ "--network=${cfg.networkName}" ] ++ rootlessHealthOptions;
      }
      // podmanRootlessConfig;
    }
    // lib.optionalAttrs cfg.enableDashboard {
      hermes-dashboard = {
        image = cfg.agentImage;
        cmd = [
          "dashboard"
          "--host"
          "0.0.0.0"
          "--insecure"
        ];
        dependsOn = [ "hermes-agent" ];
        volumes = [ "${cfg.homeVolume}:/home/hermes/.hermes" ];
        environment = cfg.extraEnvironment // {
          HERMES_HOME = "/home/hermes/.hermes";
          HERMES_UID = toString containerUid;
          HERMES_GID = toString containerGid;
          GATEWAY_HEALTH_URL = "http://hermes-agent:8642";
        };
        environmentFiles = optionalEnvFiles;
        extraOptions = [ "--network=${cfg.networkName}" ] ++ rootlessHealthOptions;
      }
      // podmanRootlessConfig;
    }
    // lib.optionalAttrs cfg.enableCaddy {
      hermes-caddy = {
        image = cfg.caddyImage;
        dependsOn = [ "hermes-webui" ];
        ports = [ "${cfg.caddyListenAddress}:${toString cfg.caddyHostPort}:80" ];
        volumes = [ "${caddyfile}:/etc/caddy/Caddyfile:ro" ];
        extraOptions = [ "--network=${cfg.networkName}" ] ++ rootlessHealthOptions;
      }
      // podmanRootlessConfig;
    };

    systemd.services.${containerUnit "hermes-agent"} = {
      requires = [ setupUnit ];
      after = [ setupUnit ];
    };

    systemd.services.${containerUnit "hermes-webui"} = {
      requires = [
        setupUnit
        (containerUnit "hermes-agent")
      ];
      after = [
        setupUnit
        (containerUnit "hermes-agent")
      ];
    };

    systemd.services.${containerUnit "hermes-dashboard"} = mkIf cfg.enableDashboard {
      requires = [
        setupUnit
        (containerUnit "hermes-agent")
      ];
      after = [
        setupUnit
        (containerUnit "hermes-agent")
      ];
    };

    systemd.services.${containerUnit "hermes-caddy"} = mkIf cfg.enableCaddy {
      requires = [
        setupUnit
        (containerUnit "hermes-webui")
      ];
      after = [
        setupUnit
        (containerUnit "hermes-webui")
      ];
    };
  };
}
