# Secret-free evaluation; does not activate a service or require real age files.
let
  evaluated = import <nixpkgs/nixos/lib/eval-config.nix> {
    system = "x86_64-linux";
    modules = [
      ../src/roles/nixos/files/etc/nixos/modules/immich.nix
      (
        { lib, ... }:
        {
          options.age.secrets = lib.mkOption {
            type = lib.types.attrsOf (
              lib.types.submodule (
                { name, ... }:
                {
                  options = {
                    file = lib.mkOption { type = lib.types.path; };
                    mode = lib.mkOption { type = lib.types.str; };
                    path = lib.mkOption {
                      type = lib.types.str;
                      default = "/run/agenix/${name}";
                    };
                  };
                }
              )
            );
          };
          config.system.stateVersion = "26.05";
        }
      )
    ];
  };
  cfg = evaluated.config;
  server = cfg.systemd.services.immich-server;
in
assert cfg.services.immich.host == "127.0.0.1";
assert !cfg.services.immich.openFirewall;
assert !(builtins.elem 3000 cfg.networking.firewall.allowedTCPPorts);
assert cfg.services.immich.settings.passwordLogin.enabled;
assert cfg.services.immich.settings.oauth.enabled;
assert !cfg.services.immich.settings.oauth.autoLaunch;
assert
  cfg.services.immich.settings.oauth.clientSecret._secret == "/run/agenix/immich_oidc_client_secret";
assert cfg.services.immich.settings.oauth.clientId._secret == "/run/agenix/immich_oidc_client_id";
assert builtins.elem "admin-password:/run/agenix/immich_admin_password"
  server.serviceConfig.LoadCredential;
assert builtins.elem "immich-server.service" cfg.systemd.services.caddy.after;
assert cfg.services.caddy.virtualHosts."immich.net.scetrov.live".useACMEHost == "scetrov.live";
assert builtins.all (secret: secret.mode == "0400") (builtins.attrValues cfg.age.secrets);
{
  inherit (cfg.services.immich)
    host
    port
    openFirewall
    settings
    ;
  packageVersion = cfg.services.immich.package.version;
  firewallPorts = cfg.networking.firewall.allowedTCPPorts;
  virtualHost = cfg.services.caddy.virtualHosts."immich.net.scetrov.live".extraConfig;
  certificate = cfg.services.caddy.virtualHosts."immich.net.scetrov.live".useACMEHost;
  caddyAfter = cfg.systemd.services.caddy.after;
  credentials = server.serviceConfig.LoadCredential;
  bootstrap = server.serviceConfig.ExecStartPost;
  umask = server.serviceConfig.UMask;
  configFile = server.environment.IMMICH_CONFIG_FILE;
  secretModes = builtins.mapAttrs (_: secret: secret.mode) cfg.age.secrets;
}
