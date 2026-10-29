{ }:
let
  pkgs = import <nixpkgs> { };
  lib = pkgs.lib;
  cfg =
    (import <nixpkgs/nixos/lib/eval-config.nix> {
      system = "x86_64-linux";
      modules = [
        ../src/roles/nixos/files/etc/nixos/modules/xrdp-crl.nix
        {
          boot.isContainer = true;
          system.stateVersion = "26.05";
          services.openssh = {
            enable = true;
            settings.AllowUsers = [ "scetrov" ];
          };
          services.caddy.enable = true;
          security.acme = {
            acceptTerms = true;
            defaults.email = "test@example.invalid";
            certs."scetrov.live".dnsProvider = "cloudflare";
          };
        }
      ];
    }).config;
  https = cfg.services.caddy.virtualHosts."https://crl.net.scetrov.live";
  http = cfg.services.caddy.virtualHosts."http://crl.net.scetrov.live";
  identity = cfg.users.users.xrdp-crl-publisher;
in
assert https.useACMEHost == "scetrov.live";
assert lib.hasInfix "not remote_ip 10.229.0.0/16 127.0.0.1 ::1" https.extraConfig;
assert lib.hasInfix "path /bullit-xrdp.crl" https.extraConfig;
assert lib.hasInfix "method GET HEAD" https.extraConfig;
assert !(lib.hasInfix "forward_auth" https.extraConfig);
assert !(lib.hasInfix "100.64.0.0/10" https.extraConfig);
assert !(lib.hasInfix "file_server" http.extraConfig);
assert lib.hasInfix "404" http.extraConfig;
assert lib.hasInfix "restrict,from=\"10.229.10.10\"" (
  builtins.head identity.openssh.authorizedKeys.keys
);
assert lib.hasInfix "ForceCommand internal-sftp" cfg.services.openssh.extraConfig;
assert lib.hasInfix "ChrootDirectory /var/lib/xrdp-crl" cfg.services.openssh.extraConfig;
assert lib.hasInfix "DisableForwarding yes" cfg.services.openssh.extraConfig;
assert builtins.elem "scetrov" cfg.services.openssh.settings.AllowUsers;
assert builtins.elem "xrdp-crl-publisher" cfg.services.openssh.settings.AllowUsers;
assert cfg.systemd.services.xrdp-crl-monitor.serviceConfig.User == "xrdp-crl-monitor";
assert
  cfg.systemd.services.xrdp-crl-monitor.unitConfig.ConditionPathExists
  == "/var/lib/xrdp-crl/upload/bullit-xrdp.crl";
{
  passed = true;
  caddySyntax =
    pkgs.runCommand "xrdp-crl-caddy-syntax"
      {
        nativeBuildInputs = [ pkgs.caddy ];
      }
      ''
        caddy adapt --adapter caddyfile --config ${cfg.environment.etc."caddy/caddy_config".source} > "$out"
      '';
}
