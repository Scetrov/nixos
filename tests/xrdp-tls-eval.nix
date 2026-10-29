# nix-instantiate --eval --strict --expr 'import ./tests/xrdp-tls-eval.nix {}'
{ }:
let
  cfg =
    (import <nixpkgs/nixos/lib/eval-config.nix> {
      system = "x86_64-linux";
      modules = [
        ../src/roles/nixos/files/etc/nixos/modules/xrdp-tls.nix
        ({ lib, ... }: {
          options.age.secrets = lib.mkOption {
            type = lib.types.attrs;
            default = { };
          };
          config = {
            boot.isContainer = true;
            system.stateVersion = "26.05";
            services.xrdp.enable = true;
            age.secrets = {
              xrdp_ca_cert.path = "/run/agenix/xrdp_ca_cert";
              xrdp_ca_key.path = "/run/agenix/xrdp_ca_key";
            };
          };
        })
      ];
    }).config;
  libHas = (import <nixpkgs> { }).lib.hasInfix;
  service = cfg.systemd.services.xrdp;
  renew = cfg.systemd.services.xrdp-tls-renew;
in
assert cfg.services.xrdp.sslCert == "/var/lib/xrdp-tls/current/cert.pem";
assert cfg.services.xrdp.sslKey == "/var/lib/xrdp-tls/current/key.pem";
assert builtins.elem "xrdp-tls-renew.service" service.requires;
assert builtins.elem "xrdp-tls-renew.service" service.after;
assert builtins.all (
  unit: builtins.hasAttr (builtins.replaceStrings [ ".service" ] [ "" ] unit) cfg.systemd.services
) renew.requires;
assert builtins.elem "xrdp.service" renew.before;
assert !(libHas "req -x509" service.preStart);
assert libHas "test -s /var/lib/xrdp-tls/current/key.pem" service.preStart;
assert libHas "security_layer=tls" cfg.services.xrdp.extraConfDirCommands;
assert renew.serviceConfig.ProtectSystem == "strict";
assert cfg.systemd.timers.xrdp-tls-renew.timerConfig.Persistent;
assert cfg.systemd.timers.xrdp-tls-renew.timerConfig.OnCalendar == "daily";
{
  passed = true;
}
