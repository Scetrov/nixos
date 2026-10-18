{
  pkgs ? import <nixpkgs> { },
}:

let
  lib = pkgs.lib;
  ageStub =
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
                path = lib.mkOption {
                  type = lib.types.str;
                  default = "/run/agenix/${name}";
                };
                owner = lib.mkOption {
                  type = lib.types.str;
                  default = "root";
                };
                group = lib.mkOption {
                  type = lib.types.str;
                  default = "root";
                };
                mode = lib.mkOption {
                  type = lib.types.str;
                  default = "0400";
                };
              };
            }
          )
        );
      };
    };
  appStub =
    { lib, ... }:
    {
      options.services.hermes-webui.enable = lib.mkEnableOption "stub";
      options.scetrov.services.home-assistant.enable = lib.mkEnableOption "stub";
    };
  evaluated = import <nixpkgs/nixos/lib/eval-config.nix> {
    system = "x86_64-linux";
    modules = [
      ageStub
      appStub
      ../files/etc/nixos/modules/garage.nix
      ../files/etc/nixos/modules/prometheus.nix
      ../files/etc/nixos/modules/caddy.nix
      ../files/etc/nixos/modules/local-networking.nix
      {
        system.stateVersion = "26.05";
        services.grafana.enable = true;
        security.acme.acceptTerms = true;
        security.acme.defaults.email = "ops@example.test";
        security.acme.certs."scetrov.live".domain = "scetrov.live";
        security.acme.certs."s3.tailnet.net.scetrov.live".domain = "s3.tailnet.net.scetrov.live";
      }
    ];
  };
  config = evaluated.config;
  garage = config.services.garage;
  garageService = config.systemd.services.garage;
  s3Vhost = config.services.caddy.virtualHosts."s3.tailnet.net.scetrov.live";
  internalS3Vhost = config.services.caddy.virtualHosts."s3.net.scetrov.live";
  adminVhost = config.services.caddy.virtualHosts."garage-admin.net.scetrov.live";
  scrapeJobs = map (job: job.job_name) config.services.prometheus.scrapeConfigs;
in
assert lib.assertMsg garage.enable "Garage must be enabled";
assert lib.assertMsg (
  garage.package == evaluated.pkgs.garage_2 && garage.package.version == "2.4.1"
) "Garage must use pkgs.garage_2 at version 2.4.1";
assert lib.assertMsg (
  garage.settings.data_dir == "/var/lib/garage/data"
  && garage.settings.metadata_dir == "/var/lib/garage/meta"
  && garage.settings.data_fsync
  && garage.settings.metadata_fsync
  && garageService.serviceConfig.StateDirectory == "garage"
  && garageService.serviceConfig.StateDirectoryMode == "0750"
  && garageService.serviceConfig.UMask == "0077"
) "Garage persistent storage or service hardening changed";
assert lib.assertMsg (
  garage.settings.s3_api.api_bind_addr == "127.0.0.1:3900"
  && garage.settings.admin.api_bind_addr == "127.0.0.1:3903"
  && garage.settings.admin.metrics_require_token
  && !(builtins.hasAttr "s3_web" garage.settings)
) "Garage must expose no anonymous website endpoint and keep APIs loopback-only";
assert lib.assertMsg (
  config.age.secrets.garage_rpc_secret.mode == "0400"
  && config.age.secrets.garage_admin_environment.mode == "0400"
  && config.age.secrets.garage_metrics_token.group == "prometheus"
  && config.age.secrets.garage_metrics_token.mode == "0440"
  && config.age.secrets.garage_metrics_environment.mode == "0400"
  && builtins.elem "/run/agenix/garage_admin_environment" garageService.serviceConfig.EnvironmentFile
  && builtins.elem "/run/agenix/garage_metrics_environment" garageService.serviceConfig.EnvironmentFile
) "Garage secrets must be injected with restricted filesystem permissions";
assert lib.assertMsg (
  lib.hasInfix "@notTailnet not remote_ip 100.64.0.0/10" s3Vhost.extraConfig
  && lib.hasInfix ''respond @notTailnet "Forbidden" 403'' s3Vhost.extraConfig
  && lib.hasInfix "reverse_proxy 127.0.0.1:3900" s3Vhost.extraConfig
  && !(builtins.elem 3900 config.networking.firewall.allowedTCPPorts)
  && !(builtins.elem 3903 config.networking.firewall.allowedTCPPorts)
) "Garage S3 and admin APIs must not receive direct firewall exposure";
assert lib.assertMsg (
  internalS3Vhost.useACMEHost == "scetrov.live"
  && lib.hasInfix "@notInternal not remote_ip 10.229.0.0/16 127.0.0.0/24 100.64.0.0/10" internalS3Vhost.extraConfig
  && lib.hasInfix ''respond @notInternal "Forbidden" 403'' internalS3Vhost.extraConfig
  && lib.hasInfix "reverse_proxy 127.0.0.1:3900" internalS3Vhost.extraConfig
  && builtins.elem "s3.net.scetrov.live" config.networking.hosts."10.229.10.2"
) "Internal S3 must retain peer filtering, the Garage upstream, wildcard TLS and its LAN alias";
assert lib.assertMsg (builtins.elem "garage" scrapeJobs) "Prometheus must scrape Garage metrics";
assert lib.assertMsg (
  adminVhost.useACMEHost == "scetrov.live"
  && lib.hasInfix "route {" adminVhost.extraConfig
  && lib.hasInfix "@notInternal not remote_ip 10.229.0.0/16 127.0.0.0/24 100.64.0.0/10" adminVhost.extraConfig
  && lib.hasInfix ''respond @notInternal "Forbidden" 403'' adminVhost.extraConfig
  && lib.hasInfix "forward_auth http://127.0.0.1:9000" adminVhost.extraConfig
  && lib.hasInfix "reverse_proxy 127.0.0.1:3903" adminVhost.extraConfig
  && lib.hasInfix ''header_up Authorization "Bearer {$GARAGE_ADMIN_AUTOMATION_TOKEN}"'' adminVhost.extraConfig
  && !(lib.hasInfix "reverse_proxy 127.0.0.1:3903" internalS3Vhost.extraConfig)
  && config.age.secrets.garage_admin_automation_token.owner == "caddy"
  && config.age.secrets.garage_admin_automation_token.mode == "0400"
  && builtins.elem "garage-admin.net.scetrov.live" config.networking.hosts."10.229.10.2"
  && garage.settings.admin.api_bind_addr == "127.0.0.1:3903"
) "Garage admin broker must stay private, ordered, and loopback-upstream";
{
  passed = true;
  s3Bind = s3Vhost.listenAddresses;
  metricsTarget = "127.0.0.1:3903";
}
