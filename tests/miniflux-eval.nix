# Evaluate without production credentials or activating any host services.
{
  enable ? true,
  grafanaEnable ? true,
  subscriptionsEnable ? false,
}:
let
  evaluated = import <nixpkgs/nixos/lib/eval-config.nix> {
    system = "x86_64-linux";
    modules = [
      ../src/roles/nixos/files/etc/nixos/modules/miniflux.nix
      ../src/roles/nixos/files/etc/nixos/modules/local-networking.nix
      ../src/roles/nixos/files/etc/nixos/modules/alloy.nix
      (
        { lib, ... }:
        {
          options = {
            age.secrets = lib.mkOption {
              type = lib.types.attrsOf (
                lib.types.submodule (
                  { name, ... }:
                  {
                    options = {
                      file = lib.mkOption { type = lib.types.path; };
                      mode = lib.mkOption {
                        type = lib.types.str;
                        default = "0400";
                      };
                      owner = lib.mkOption {
                        type = lib.types.str;
                        default = "root";
                      };
                      path = lib.mkOption {
                        type = lib.types.str;
                        default = "/run/agenix/${name}";
                      };
                    };
                  }
                )
              );
              default = { };
            };
            scetrov.services.authentik.enable = lib.mkEnableOption "fixture shared database";
          };
          config = {
            system.stateVersion = "26.05";
            scetrov.services.authentik.enable = true;
            scetrov.services.miniflux = {
              inherit enable;
              subscriptions = {
                enable = subscriptionsEnable;
                toolFile = ../scripts/miniflux_subscriptions.py;
                catalogueFile = ../config/miniflux/feeds.json;
              };
            };
            networking.hostName = "habiki";
            services.grafana.enable = grafanaEnable;
            services.prometheus.enable = true;
          };
        }
      )
    ];
  };
  cfg = evaluated.config;
  liblessUnits = builtins.listToAttrs (
    map
      (name: {
        inherit name;
        value = {
          inherit (cfg.systemd.services.${name})
            wantedBy
            restartTriggers
            restartIfChanged
            stopIfChanged
            after
            requisite
            ;
          config = cfg.systemd.services.${name}.serviceConfig;
        };
      })
      (
        builtins.filter (name: builtins.match "miniflux-subscriptions.*" name != null) (
          builtins.attrNames cfg.systemd.services
        )
      )
  );
in
{
  subscriptionUnits = liblessUnits;
  enabled = cfg.services.miniflux.enable;
  localDatabase = cfg.services.postgresql.enable;
  packageVersion = cfg.services.miniflux.package.version;
  packageDrvPath = cfg.services.miniflux.package.drvPath;
  environment = if enable then cfg.systemd.services.miniflux.environment else { };
  credentials = if enable then cfg.systemd.services.miniflux.serviceConfig.LoadCredential else [ ];
  ordering =
    if enable then
      {
        requires = cfg.systemd.services.miniflux.requires;
        after = cfg.systemd.services.miniflux.after;
        partOf = cfg.systemd.services.miniflux.partOf;
        setupAfter = cfg.systemd.services.miniflux-dbsetup.after;
        setupWants = cfg.systemd.services.miniflux-dbsetup.wants;
      }
    else
      { };
  virtualHosts = builtins.attrNames cfg.services.caddy.virtualHosts;
  caddyConfig =
    if enable then cfg.services.caddy.virtualHosts."feed.net.scetrov.live".extraConfig else "";
  caddyCertificate =
    if enable then cfg.services.caddy.virtualHosts."feed.net.scetrov.live".useACMEHost else "";
  scrapeConfigs = builtins.filter (
    scrape: scrape.job_name == "miniflux"
  ) cfg.services.prometheus.scrapeConfigs;
  alerting = cfg.services.grafana.provision.alerting.rules.settings;
  journalConfig = cfg.environment.etc."alloy/config.alloy".text;
  aliases = cfg.networking.hosts."10.229.10.2";
  secretNames = builtins.filter (name: builtins.match "miniflux.*" name != null) (
    builtins.attrNames cfg.age.secrets
  );
  serviceNames = builtins.filter (name: builtins.match "miniflux.*" name != null) (
    builtins.attrNames cfg.systemd.services
  );
}
