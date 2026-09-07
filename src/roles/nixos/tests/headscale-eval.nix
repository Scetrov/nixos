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
      options.scetrov.services.home-assistant.enable = lib.mkEnableOption "stub";
      options.services.hermes-webui.enable = lib.mkEnableOption "stub";
    };
  evaluated = import <nixpkgs/nixos/lib/eval-config.nix> {
    system = "x86_64-linux";
    modules = [
      ageStub
      appStub
      ../files/etc/nixos/modules/headscale.nix
      ../files/etc/nixos/modules/caddy.nix
      ../files/etc/nixos/modules/prometheus.nix
      {
        system.stateVersion = "26.05";
        services.grafana.enable = true;
        security.acme.acceptTerms = true;
        security.acme.defaults.email = "ops@example.test";
        security.acme.certs."scetrov.live".domain = "scetrov.live";
      }
    ];
  };
  config = evaluated.config;
  caddyVhost = config.services.caddy.virtualHosts."headscale.net.scetrov.live:8443";
  scrapeJobs = map (job: job.job_name) config.services.prometheus.scrapeConfigs;
in
assert lib.assertMsg (
  config.services.headscale.address == "127.0.0.1"
) "Headscale must bind only to loopback";
assert lib.assertMsg (
  config.services.headscale.port == 8090
  && config.services.headscale.settings.database.sqlite.path == "/var/lib/headscale/db.sqlite"
  && config.services.headscale.settings.database.sqlite.write_ahead_log
  && config.systemd.services.headscale.serviceConfig.StateDirectory == "headscale"
) "Headscale persistent SQLite state wiring changed";
assert lib.assertMsg (
  config.systemd.services.headscale.serviceConfig.User == "headscale"
  && config.systemd.services.headscale.serviceConfig.ProtectSystem == "strict"
) "Headscale service ownership or hardening changed";
assert lib.assertMsg (
  config.services.headscale.settings.server_url == "https://headscale.net.scetrov.live:8443"
  && config.services.headscale.settings.metrics_listen_addr == "127.0.0.1:9091"
) "Headscale public URL or metrics binding changed";
assert lib.assertMsg (
  config.services.cloudflare-ddns.ip4Domains == [ "headscale.net.scetrov.live" ]
  && config.services.cloudflare-ddns.provider.ipv6 == "none"
  && config.age.secrets.cloudflare_headscale_ddns_api_token.owner == "cloudflare-ddns"
) "Headscale DDNS must be IPv4-only and use its restricted credential";
assert lib.assertMsg (
  builtins.elem 8443 config.networking.firewall.allowedTCPPorts
  && caddyVhost.useACMEHost == "scetrov.live"
  && lib.hasInfix "reverse_proxy 127.0.0.1:8090" caddyVhost.extraConfig
  && !(lib.hasInfix "forward_auth" caddyVhost.extraConfig)
) "Headscale ingress must be narrow and bypass generic proxy authentication";
assert lib.assertMsg (lib.hasInfix "\"acls\": []"
  config.environment.etc."headscale/policy.hujson".text
) "Headscale policy must default-deny traffic";
assert lib.assertMsg (
  builtins.elem "headscale" scrapeJobs
  && builtins.elem "headscale-edge" scrapeJobs
  && config.services.prometheus.exporters.blackbox.enable
  && config.systemd.services.prometheus.serviceConfig.ExecStart != [ ]
) "Headscale metrics and public availability monitoring are required";
{
  passed = true;
  serviceAddress = config.services.headscale.address;
  publicUrl = config.services.headscale.settings.server_url;
}
