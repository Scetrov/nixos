{
  pkgs ? import <nixpkgs> { },
}:
let
  lib = pkgs.lib;
  ageStub = { lib, ... }: {
    options.age.secrets = lib.mkOption {
      default = { };
      type = lib.types.attrsOf (
        lib.types.submodule (
          { name, ... }: {
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
  evaluated = import <nixpkgs/nixos/lib/eval-config.nix> {
    system = "x86_64-linux";
    modules = [
      ageStub
      ../files/etc/nixos/modules/project-zomboid.nix
      {
        system.stateVersion = "26.05";
        scetrov.services.project-zomboid = {
          enable = true;
          steamAccount = "test-account";
          steamcmdPath = "/bin/true";
          adminPasswordFile = ./project-zomboid-eval.nix;
          joinPasswordFile = ./project-zomboid-eval.nix;
        };
      }
    ];
  };
  config = evaluated.config;
  service = config.systemd.services.project-zomboid;
in
assert lib.assertMsg (
  config.users.users.project-zomboid.isSystemUser
  && config.users.users.project-zomboid.home == "/var/lib/project-zomboid"
) "service identity must be unprivileged and persistent";
assert lib.assertMsg
  (builtins.elem "d /var/lib/project-zomboid 0750 project-zomboid project-zomboid - -" config.systemd.tmpfiles.rules)
  "state directory must be service-owned";
assert lib.assertMsg (
  service.serviceConfig.Restart == "on-failure"
  && service.serviceConfig.TimeoutStopSec == 120
  && service.serviceConfig.MemoryMax == "4G"
) "lifecycle resource limits changed";
assert lib.assertMsg (
  config.age.secrets.project_zomboid_admin_password.owner == "project-zomboid"
  && config.age.secrets.project_zomboid_join_password.mode == "0400"
) "agenix secret references must be restricted";
assert lib.assertMsg (
  lib.hasInfix "10.229.0.0/16" config.networking.firewall.extraCommands
  && lib.hasInfix "--dport 16261" config.networking.firewall.extraCommands
  && lib.hasInfix "--dport 16262" config.networking.firewall.extraCommands
  && !(lib.hasInfix "27015" config.networking.firewall.extraCommands)
) "firewall must expose only LAN gameplay ports";
assert lib.assertMsg (
  !config.scetrov.services.project-zomboid.enableHeadscaleAccess
  && !(lib.hasInfix "tailscale" config.networking.firewall.extraCommands)
) "Headscale access must be disabled by default";
assert lib.assertMsg (
  config.systemd.timers.project-zomboid-backup.timerConfig.OnCalendar == "*-*-* 04:00:00"
  && config.systemd.timers.project-zomboid-restart.timerConfig.OnCalendar == "Mon *-*-* 04:15:00"
  && config.systemd.services.project-zomboid-restart.serviceConfig.ExecStart != ""
) "maintenance timers must include daily backups and weekly graceful restarts";
{
  passed = true;
  # Expose rendered scripts so the shell/behavior tests can build them.
  launchScript = service.serviceConfig.ExecStart;
  maintenanceScript = builtins.substring 0 (
    builtins.stringLength config.systemd.services.project-zomboid-backup.serviceConfig.ExecStart - 7
  ) config.systemd.services.project-zomboid-backup.serviceConfig.ExecStart;
}
