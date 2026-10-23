# Read-only evaluation: no vault, production secret files, or service activation.
{
  enable ? true,
}:
let
  evaluated = import <nixpkgs/nixos/lib/eval-config.nix> {
    system = "x86_64-linux";
    modules = [
      ../src/roles/nixos/files/etc/nixos/modules/filebrowser.nix
      ../src/roles/nixos/files/etc/nixos/modules/local-networking.nix
      ../src/roles/nixos/files/etc/nixos/modules/alloy.nix
      ../src/roles/nixos/files/etc/nixos/modules/prometheus.nix
      (
        { lib, ... }:
        {
          options.age.secrets = lib.mkOption {
            default = { };
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
          };
          config = {
            system.stateVersion = "26.05";
            services.grafana.enable = true;
            services.grafana.settings.security.secret_key = "$__file{/run/fixture/grafana-key}";
            security.acme.acceptTerms = true;
            security.acme.defaults.email = "fixture@example.invalid";
            security.acme.certs."scetrov.live".webroot = "/var/empty";
            fileSystems."/" = {
              device = "/dev/test-fixture";
              fsType = "ext4";
            };
            boot.loader.grub.devices = [ "nodev" ];
            scetrov.services.filebrowser = {
              inherit enable;
              enrollmentsFile = ../src/filebrowser-enrollments.json;
              toolDirectory = ../scripts;
            };
          };
        }
      )
    ];
  };
  cfg = evaluated.config;
in
{
  containers = cfg.virtualisation.oci-containers.containers;
  alerting = cfg.services.grafana.provision.alerting.rules.settings;
  scrapeConfigs = cfg.services.prometheus.scrapeConfigs;
  journalConfig = cfg.environment.etc."alloy/config.alloy".text;
  aliases = cfg.networking.hosts."10.229.10.2";
  caddyRoute =
    if enable then cfg.services.caddy.virtualHosts."files.net.scetrov.live".extraConfig else "";
  secrets = builtins.attrNames cfg.age.secrets;
  units = builtins.attrNames cfg.systemd.services;
  credentials =
    if enable then cfg.systemd.services.podman-filebrowser.serviceConfig.LoadCredential else [ ];
  preparation = if enable then cfg.systemd.services.podman-filebrowser.preStart else "";
  serviceUid = if enable then cfg.users.users.filebrowser.uid else null;
  assertions = builtins.filter (assertion: !assertion.assertion) cfg.assertions;
}
