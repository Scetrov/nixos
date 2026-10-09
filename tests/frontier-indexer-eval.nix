# Minimal NixOS evaluation fixture: no production secrets or host activation.
let
  evaluated = import <nixpkgs/nixos/lib/eval-config.nix> {
    system = "x86_64-linux";
    modules = [
      ../src/roles/nixos/files/etc/nixos/modules/frontier-indexer.nix
      (
        {
          config,
          lib,
          pkgs,
          ...
        }:
        {
          options.age.secrets = lib.mkOption {
            type = lib.types.attrsOf (
              lib.types.submodule {
                options = {
                  file = lib.mkOption { type = lib.types.path; };
                  owner = lib.mkOption { type = lib.types.str; };
                  path = lib.mkOption {
                    type = lib.types.str;
                    default = "/tmp/frontier-indexer-test-secret";
                  };
                };
              }
            );
            default = { };
          };
          config = {
            system.stateVersion = "26.05";
            scetrov.services.frontier-indexer =
              (import ../src/roles/nixos/files/device-configuration/habiki.nix { inherit config pkgs; })
              .scetrov.services.frontier-indexer;
          };
        }
      )
    ];
  };
  names = [
    "frontier-indexer-prepare-env"
    "frontier-indexer-network"
    "frontier-indexer-wait-for-db"
    "frontier-indexer-db-preflight"
    "frontier-indexer-schema-reset"
    "podman-frontier-timescaledb"
    "podman-frontier-indexer"
  ];
  cfg = evaluated.config;
in
{
  settings = cfg.scetrov.services.frontier-indexer;
  containers = cfg.virtualisation.oci-containers.containers;
  services = builtins.listToAttrs (
    map (name: {
      inherit name;
      value = {
        inherit (cfg.systemd.services.${name}) requires after before;
        execStart = cfg.systemd.services.${name}.serviceConfig.ExecStart;
      };
    }) names
  );
  scripts = evaluated.pkgs.linkFarm "frontier-indexer-test-scripts" (
    map
      (name: {
        inherit name;
        path = cfg.systemd.services.${name}.serviceConfig.ExecStart;
      })
      [
        "frontier-indexer-db-preflight"
        "frontier-indexer-schema-reset"
        "frontier-indexer-prepare-env"
      ]
  );
}
