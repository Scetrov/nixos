# Evaluate the shared Caddy/DNS contract without credentials or host activation.
let
  evaluated = import <nixpkgs/nixos/lib/eval-config.nix> {
    system = "x86_64-linux";
    modules = [
      ../src/roles/nixos/files/etc/nixos/modules/caddy.nix
      ../src/roles/nixos/files/etc/nixos/modules/local-networking.nix
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
                      owner = lib.mkOption { type = lib.types.str; };
                      group = lib.mkOption {
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
            services.hermes-webui.enable = lib.mkEnableOption "fixture Hermes";
            scetrov.services.home-assistant.enable = lib.mkEnableOption "fixture Home Assistant";
          };
          config = {
            system.stateVersion = "26.05";
            services.grafana.enable = true;
            networking.hostName = "habiki";
          };
        }
      )
    ];
  };
  cfg = evaluated.config;
  host = cfg.services.caddy.virtualHosts."artcraft.net.scetrov.live";
in
assert host.useACMEHost == "scetrov.live";
assert builtins.elem "artcraft.net.scetrov.live" cfg.networking.hosts."10.229.10.2";
assert host.logFormat == "output stderr\nformat json\n";
assert
  cfg.networking.firewall.allowedTCPPorts == [
    80
    443
    8443
  ];
{
  certificate = host.useACMEHost;
  route = host.extraConfig;
  logging = host.logFormat;
  aliases = cfg.networking.hosts."10.229.10.2";
}
