{
  pkgs ? import <nixpkgs> { },
}:
let
  inherit (pkgs) lib;
  evaluate =
    enabled:
    import <nixpkgs/nixos/lib/eval-config.nix> {
      system = "x86_64-linux";
      modules = [
        ../files/etc/nixos/modules/forgejo.nix
        {
          options.age.secrets = lib.mkOption {
            default = { };
            type = lib.types.attrsOf (
              lib.types.submodule (
                { name, ... }: {
                  freeformType = lib.types.attrsOf lib.types.anything;
                  options.path = lib.mkOption {
                    type = lib.types.str;
                    default = "/run/agenix/${name}";
                  };
                }
              )
            );
          };
          config = {
            system.stateVersion = "26.05";
            networking.hostName = "habiki";
            scetrov.services.forgejo.enable = true;
            scetrov.services.forgejo.mirrors.enable = enabled;
          };
        }
      ];
    };
  disabled = (evaluate false).config;
  enabled = (evaluate true).config;
  cfg = enabled.scetrov.services.forgejo.mirrors;
  service = enabled.systemd.services.forgejo-mirrors;
in
assert !(disabled.systemd.services ? forgejo-mirrors);
assert !(disabled.systemd.timers ? forgejo-mirrors);
assert !(disabled.users.users ? forgejo-mirrors);
assert !(disabled.age.secrets ? forgejo_mirrors_token);
assert cfg.reportOnly && !cfg.importApproved && !cfg.lfsVerified && !cfg.githubCredential;
assert
  map (p: p.namespace) cfg.policies == [
    "gh-Scetrov"
    "gh-RichardSlater"
    "gh-storytold"
  ];
assert lib.all (
  p: !p.includePrivate && !p.includeForks && !p.includeArchived && p.namespaceId == null
) cfg.policies;
assert service.serviceConfig.User == "forgejo-mirrors";
assert service.serviceConfig.StateDirectoryMode == "0700";
assert service.serviceConfig.ProtectSystem == "strict";
assert service.serviceConfig.LoadCredential == [ "forgejo:/run/agenix/forgejo_mirrors_token" ];
assert service.serviceConfig.TimeoutStartSec == "45min";
assert builtins.elem "forgejo.service" service.after;
assert enabled.systemd.timers.forgejo-mirrors.timerConfig.Persistent;
assert enabled.services.forgejo.lfs.enable;
assert enabled.services.forgejo.settings.server.LFS_START_SERVER;
assert enabled.services.forgejo.lfs.contentDir == "/var/lib/forgejo/data/lfs";
assert !disabled.services.forgejo.lfs.enable;
assert !enabled.services.forgejo.settings.actions.ENABLED;
assert enabled.networking.firewall.allowedTCPPorts == disabled.networking.firewall.allowedTCPPorts;
assert enabled.services.caddy.virtualHosts == disabled.services.caddy.virtualHosts;
{
  passed = true;
  version = pkgs.forgejo.version;
}
