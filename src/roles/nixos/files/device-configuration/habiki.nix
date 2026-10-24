{ config, pkgs, ... }:

{
  imports = [
    ./modules/acme.nix
    ./modules/authentik.nix
    ./modules/blocky.nix
    ./modules/caddy.nix
    ./modules/dependency-track.nix
    ./modules/frontier-indexer.nix
    ./modules/forgejo.nix
    ./modules/grafana.nix
    ./modules/immich.nix
    ./modules/k6.nix
    ./modules/local-networking.nix
    ./modules/loki.nix
    ./modules/mimir.nix
    ./modules/miniflux.nix
    ./modules/garage.nix
    ./modules/oncall.nix
    ./modules/pyroscope.nix
    ./modules/prometheus.nix
    ./modules/project-zomboid.nix
    ./modules/tempo.nix
    ./modules/hermes.nix
    ./modules/headscale.nix
    ./modules/filebrowser.nix
    ./modules/user-scetrov-syncthing.nix
    ./modules/grafana-mcp.nix
    ./modules/github-repository-observability.nix
    ./modules/ai-usage.nix
    ./modules/home-assistant.nix
    ./modules/unifi-network-logs.nix
  ];

  boot.kernelParams = [ "pcie_aspm=performance" ];

  services.hermes-webui = {
    enable = true;
    # Hermes WebUI's current image re-execs through su during startup and fails
    # under rootless Podman on Habiki, so keep this stack rootful for now.
    rootless = false;
    enableDashboard = false;
    enableCaddy = false;
    # Native runtime heartbeat is absent from the old 0.16.0 gateway. Keep
    # source separate from persistent home: reusing hermes-agent-src masks
    # the new image's /opt/hermes with the old gateway and virtualenv.
    agentImage = "docker.io/nousresearch/hermes-agent:v2026.9.24@sha256:fca358f12efd65bfaaca05884166f15c0e2788375ca30d77061ac1ebc96452b7";
    agentSourceVolume = "hermes-agent-src-v2026-9-24";
    caddyListenAddress = "127.0.0.1";
    environmentFile = config.age.secrets.hermes_webui_env.path;
    localQwen = {
      # Operator-confirmed endpoint on a protected trusted network path.
      # Vault key and both-container endpoint discovery verified before activation.
      enable = true;
      baseUrl = "http://10.229.2.10:9931/v1";
      model = "qwen3.8-27b";
      contextLength = 65536;
      requireApiKey = true;
    };
    extraEnvironment = {
      HERMES_WEBUI_TRUSTED_PROXY_AUTH_HEADER = "X-Authentik-Username";
      HERMES_WEBUI_TRUSTED_PROXY_NETS = "127.0.0.0/8, 10.0.0.0/8";
    };
  };

  age.secrets.hermes_webui_env = {
    file = /root/secrets/hermes_webui_env.age;
    owner = if config.services.hermes-webui.rootless then config.services.hermes-webui.user else "root";
  };

  scetrov.services.authentik.enable = true;
  scetrov.services.filebrowser.enable = true;
  scetrov.services.miniflux.enable = true;
  scetrov.services.miniflux.subscriptions.enable = true;
  scetrov.services.forgejo.enable = true;
  # Approved public-only inventory; native LFS and its warning/recovery path verified.
  scetrov.services.forgejo.mirrors = {
    enable = true;
    reportOnly = false;
    importApproved = true;
    lfsVerified = true;
    privateAuthVerified = false;
    staleAfterSeconds = 10800;
    policies = [
      {
        owner = "Scetrov";
        ownerId = 144595937;
        namespace = "gh-Scetrov";
        namespaceId = 6;
      }
      {
        owner = "RichardSlater";
        ownerId = 630786;
        namespace = "gh-RichardSlater";
        namespaceId = 4;
      }
      {
        owner = "storytold";
        ownerId = 76897702;
        pattern = "*craft";
        namespace = "gh-storytold";
        namespaceId = 3;
      }
    ];
  };
  # Actions/runner is deferred; retain experimental code without activating it.
  scetrov.services.forgejo.runner.enable = false;
  scetrov.services.dependency-track.enable = true;
  scetrov.services.github-sbom-collector = {
    enable = true;
    reportOnly = false;
    githubAppId = 5385731;
    githubInstallationIds = [ 173146141 ];
    sources = [
      {
        repository = "Scetrov/efctl";
        repositoryId = 1166984576;
        workflowId = 238717662;
        branch = "main";
        artifact = "cyclonedx-sbom-v1";
        path = "bom.json";
        project = "3761ac8d-a1ce-4b1e-bfa6-7ae29141160a";
        version = "main";
      }
    ];
  };
  scetrov.services.home-assistant = {
    enable = true;
    bluetooth.enable = true;
    matter.enable = true;
  };
  scetrov.services.unifi-network-logs.enable = true;
  scetrov.services.project-zomboid = {
    enable = true;
    serverName = "pz-server";
    lanCidrs = [ "10.229.0.0/16" ];
    maxPlayers = 8;
    memoryMax = "4G";
    corpseRemovalHours = 140;
    maximumLootedBuildingChance = 0;
    zombiePopulationStartMultiplier = 0.7;
    zombiePopulationPeakMultiplier = 1.0;
    zombieRedistributeHours = 24;
    steamAccount = "ScetrovZomboid";
    adminPasswordFile = config.age.secrets.project_zomboid_admin_password.path;
    joinPasswordFile = config.age.secrets.project_zomboid_join_password.path;
  };
  scetrov.services.frontier-indexer = {
    enable = true;
    indexerImage = "ghcr.io/algo-net/frontier-indexer:v0.5.0@sha256:1d108d4538522c3bace60f792475bd808e44f09a6bff911c1afce6406811e74f";
    firstCheckpoint = "387251154";
    ingestConcurrencyMax = 32;
    resetSchemaGeneration = 7;
  };
  services.grafana-mcp = {
    enable = true;
  };
  scetrov.services.ai-usage = {
    enable = true;
    codexAppServer.enable = true;
  };

  scetrov.services.github-repository-observability = {
    enable = true;
    owners = [
      "Scetrov"
      "RichardSlater"
    ];
    includeArchived = false;
    includeForks = false;
    excludeRepositories = [ ];
    collectionIntervalSeconds = 900;
    listenAddress = "127.0.0.1:9177";
  };

  blocky.bindAddr = "10.229.53.2:53";

  networking = {
    networkmanager = {
      enable = true;
      plugins = [ pkgs.networkmanager-openvpn ];
    };
    hostName = "habiki";
    defaultGateway = "10.229.0.1";
    interfaces.eth0.ipv4.addresses = [
      {
        address = "10.229.10.2";
        prefixLength = 16;
      }
      {
        address = "10.229.53.2";
        prefixLength = 16;
      }
    ];
  };
}
