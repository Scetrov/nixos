# Secret-free evaluation; no deployment or real age files required.
let
  evaluated = import <nixpkgs/nixos/lib/eval-config.nix> {
    system = "x86_64-linux";
    modules = [
      ../src/roles/nixos/files/etc/nixos/modules/penpot.nix
      ../src/roles/nixos/files/etc/nixos/modules/prometheus.nix
      ({ lib, ... }: {
        options.age.secrets = lib.mkOption {
          type = lib.types.attrsOf (
            lib.types.submodule (
              { name, ... }: {
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
        config = {
          scetrov.services.penpot.enable = true;
          services.caddy.enable = true;
          system.stateVersion = "26.05";
        };
      })
    ];
  };
  cfg = evaluated.config;
  containers = cfg.virtualisation.oci-containers.containers;
  backend = containers.penpot-backend;
  site = cfg.services.caddy.virtualHosts."penpot.net.scetrov.live";
  frontend = containers.penpot-frontend;
in
assert builtins.length (builtins.attrNames containers) == 6;
assert builtins.all (c: builtins.match "docker.io/.*@sha256:[0-9a-f]{64}" c.image != null) (
  builtins.attrValues containers
);
assert builtins.all (c: c.ports == [ ]) (
  builtins.attrValues (builtins.removeAttrs containers [ "penpot-frontend" ])
);
assert frontend.ports == [ "127.0.0.1:9011:8080" ];
assert builtins.elem "--memory=4g" backend.extraOptions;
assert builtins.elem "--cpus=2" backend.extraOptions;
assert builtins.elem "--network=penpot" backend.extraOptions;
assert
  backend.environment.PENPOT_OIDC_BASE_URI
  == "https://identity.net.scetrov.live/application/o/penpot/";
assert backend.environment.PENPOT_SSRF_ALLOWED_HOSTS == "identity.net.scetrov.live";
assert !(backend.environment ? PENPOT_SECRET_KEY);
assert !(backend.environment ? PENPOT_DATABASE_PASSWORD);
assert builtins.all (s: s.mode == "0400") (builtins.attrValues cfg.age.secrets);
assert site.useACMEHost == "scetrov.live";
assert site.logFormat == null;
assert !(builtins.elem 9011 cfg.networking.firewall.allowedTCPPorts);
assert builtins.elem "penpot-prepare-env.service"
  cfg.systemd.services.podman-penpot-backend.requires;
assert builtins.length cfg.systemd.services.penpot-prepare-env.serviceConfig.LoadCredential == 4;
assert builtins.elem "d /var/lib/penpot/postgres 0700 - - -" cfg.systemd.tmpfiles.rules;
assert builtins.elem "d /var/lib/penpot/assets 0755 - - -" cfg.systemd.tmpfiles.rules;
# The Penpot alert ships as a standalone rule file (its own rule_files entry),
# NOT concatenated into the shared `rules` document, so its indentation cannot
# collide with another module's groups: key. There must be exactly one rule
# file and the shared rules document must carry no Penpot group.
assert builtins.length cfg.services.prometheus.ruleFiles == 1;
assert builtins.all (
  rule: builtins.match ".*PenpotServiceUnavailable.*" rule == null
) cfg.services.prometheus.rules;
{
  images = builtins.mapAttrs (_: c: c.image) containers;
  inherit (backend) environment;
  virtualHost = site.extraConfig;
  runtimeLogging = cfg.services.caddy.logFormat;
  healthOptions = builtins.mapAttrs (_: c: c.extraOptions) containers;
  frontendVolumes = frontend.volumes;
  readinessScrape = builtins.filter (
    s: s.job_name == "penpot-edge"
  ) cfg.services.prometheus.scrapeConfigs;
  ruleFiles = builtins.map builtins.toString cfg.services.prometheus.ruleFiles;
  rules = cfg.services.prometheus.rules;
  prepareScript = cfg.systemd.services.penpot-prepare-env.serviceConfig.ExecStart;
}
