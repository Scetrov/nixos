# Apply with {} to run assertions; no production secrets, builds or activation.
{ }:
let
  evaluate =
    tlsOnly:
    (import <nixpkgs/nixos/lib/eval-config.nix> {
      system = "x86_64-linux";
      modules = [
        ../src/roles/nixos/files/etc/nixos/modules/authentik.nix
        ({ lib, ... }: {
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
          config = {
            system.stateVersion = "26.05";
            boot.isContainer = true;
            security.acme = {
              acceptTerms = true;
              defaults.email = "test@example.invalid";
              certs."scetrov.live" = {
                dnsProvider = "cloudflare";
                reloadServices = [ "caddy.service" ];
              };
            };
            scetrov.services.authentik = {
              enable = true;
              postgresqlTLSOnly = tlsOnly;
            };
          };
        })
      ];
    }).config;
  cfg = evaluate true;
  migration = evaluate false;
  db = cfg.virtualisation.oci-containers.containers.authentik-postgresql;
  prepare = cfg.systemd.services.postgresql-tls-prepare;
  unit = cfg.systemd.services.podman-authentik-postgresql;
  contains = builtins.elem;
in
assert contains "ssl=on" db.cmd;
assert contains "hba_file=/etc/postgresql/pg_hba.conf" db.cmd;
assert contains "ssl_key_file=/run/postgresql-tls/current/key.pem" db.cmd;
assert contains "/var/lib/authentik/postgresql-tls:/run/postgresql-tls:ro" db.volumes;
assert contains "/var/lib/authentik/postgresql-data:/var/lib/postgresql/data:U" db.volumes;
assert contains "--network-alias=postgres.net.scetrov.live" db.extraOptions;
assert contains "5433:5432" db.ports;
assert contains "postgresql-tls-prepare.service" unit.after;
assert contains "postgresql-tls-prepare.service" unit.requires;
assert contains "acme-scetrov.live.service" prepare.after;
assert contains "acme-scetrov.live.service" prepare.requires;
assert prepare.serviceConfig.ExecStart == prepare.serviceConfig.ExecReload;
assert prepare.serviceConfig.RemainAfterExit;
assert contains "caddy.service" cfg.security.acme.certs."scetrov.live".reloadServices;
assert contains "postgresql-tls-prepare.service"
  cfg.security.acme.certs."scetrov.live".reloadServices;
assert cfg.scetrov.services.authentik.postgresqlTLSOnly;
assert !migration.scetrov.services.authentik.postgresqlTLSOnly;
{
  passed = true;
  checks = "Existing data mount and port retained; native TLS, private DNS, preparation ordering, reload without dependency restart, Caddy renewal consumers and explicit migration mode.";
}
