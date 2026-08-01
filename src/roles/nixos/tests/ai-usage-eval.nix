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
  evaluated = import <nixpkgs/nixos/lib/eval-config.nix> {
    system = "x86_64-linux";
    modules = [
      ageStub
      ../files/etc/nixos/modules/ai-usage.nix
      {
        system.stateVersion = "25.11";
        virtualisation.podman.enable = true;
        scetrov.services.ai-usage = {
          enable = true;
          codexAppServer.enable = true;
        };
      }
    ];
  };
  config = evaluated.config;
  container = config.virtualisation.oci-containers.containers.codex-app-server-runtime;
  containerService = config.systemd.services.podman-codex-app-server-runtime;
  exporterService = config.systemd.services.ai-usage-exporter;
  requiredOptions = [
    "--read-only"
    "--cap-drop=ALL"
    "--security-opt=no-new-privileges"
    "--userns=keep-id:uid=10001,gid=10001"
    "--group-add=keep-groups"
  ];
in
assert lib.assertMsg (
  container.image == "codex-app-server:0.145.0"
) "Codex app-server image must remain version-pinned";
assert lib.assertMsg (
  container.imageFile != null
) "Codex app-server must load the repository-built image archive";
assert lib.assertMsg (container.pull == "never") "Codex app-server must not pull a registry image";
assert lib.assertMsg (
  container.user == "10001:10001"
) "Codex app-server must run as the image's non-root identity";
assert lib.assertMsg (
  container.podman.user == "codex-app-server"
) "Podman must run rootless under the dedicated host identity";
assert lib.assertMsg (
  config.users.users.codex-app-server.uid == 979
) "Codex app-server host UID changed unexpectedly";
assert lib.assertMsg
  (builtins.elem "ai-usage-exporter" config.users.users.codex-app-server.extraGroups)
  "Codex app-server must retain the socket access group";
assert lib.assertMsg (
  container.volumes == [
    "/var/lib/codex-app-server:/var/lib/codex-app-server:rw"
    "/run/codex-app-server:/run/codex-app-server:rw"
  ]
) "Codex app-server mounts must contain only state and runtime paths";
assert lib.assertMsg (builtins.all (
  option: builtins.elem option container.extraOptions
) requiredOptions) "Codex app-server hardening or rootless mapping option is missing";
assert lib.assertMsg (
  container.networks == [ "podman" ] && container.ports == [ ]
) "Codex app-server must have outbound access without publishing a transport port";
assert lib.assertMsg (container.log-driver == "journald") "Codex app-server logs must use journald";
assert lib.assertMsg (container.autoStart) "Codex app-server must start automatically";
assert lib.assertMsg (builtins.any (
  package: lib.getName package == "codex-app-server-enroll"
) config.environment.systemPackages) "The restricted Codex enrollment helper must be installed";
assert lib.assertMsg (
  containerService.serviceConfig.Restart == "on-failure"
) "Codex app-server must restart after failure";
assert lib.assertMsg (
  containerService.serviceConfig.UMask == "0007"
) "Codex app-server service umask must protect the socket";
assert lib.assertMsg (
  builtins.length containerService.serviceConfig.ExecStartPost == 1
) "Codex app-server must have one bounded readiness post-start check";
assert lib.assertMsg (
  builtins.elem "podman-codex-app-server-runtime.service" exporterService.after
  && builtins.elem "podman-codex-app-server-runtime.service" exporterService.wants
  && !(builtins.elem "podman-codex-app-server-runtime.service" exporterService.requires)
) "Exporter ordering must not become a hard app-server dependency";
assert lib.assertMsg (
  lib.hasInfix "--codex-socket /run/codex-app-server/control.sock" exporterService.script
  && !(lib.hasInfix "--codex-secret-file" exporterService.script)
  && !(builtins.hasAttr "codex_oauth" config.age.secrets)
) "Exporter must use only app-server with no legacy Codex credential declaration";
assert lib.assertMsg (
  builtins.elem "d /var/lib/codex-app-server 0700 codex-app-server codex-app-server - -" config.systemd.tmpfiles.rules
  && builtins.elem "d /run/codex-app-server 2770 codex-app-server ai-usage-exporter - -" config.systemd.tmpfiles.rules
) "Codex state or runtime directory permissions differ from the design";
assert lib.assertMsg (builtins.all
  (
    rule:
    !(lib.hasPrefix "Z /var/lib/codex-app-server" rule)
    && !(lib.hasPrefix "Z /run/codex-app-server" rule)
  )
  config.systemd.tmpfiles.rules
) "Recursive tmpfiles rules must not corrupt Podman storage or credential-state modes";
{
  passed = true;
  image = container.image;
  rootlessUser = container.podman.user;
  networks = container.networks;
  publishedPorts = container.ports;
}
