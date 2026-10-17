{
  config,
  lib,
  pkgs,
  ...
}:

let
  # NixOS 26.05's Immich 2.7.5 is blocked as insecure. Use the existing
  # nixos-unstable channel for the supported 3.x release until 26.05 is
  # refreshed; the NixOS service module remains package-compatible.
  unstable = import <nixos-unstable> { };
in
{
  services.immich = {
    enable = true;
    package = unstable.immich;
    port = 3000;
    host = "127.0.0.1";
    openFirewall = false;
    settings = {
      oauth = {
        enabled = true;
        issuerUrl = "https://identity.net.scetrov.live/application/o/immich/";
        clientId._secret = config.age.secrets.immich_oidc_client_id.path;
        clientSecret._secret = config.age.secrets.immich_oidc_client_secret.path;
        scope = "openid email profile";
        buttonText = "Sign in with Authentik";
        autoRegister = true;
        autoLaunch = false;
      };
      passwordLogin.enabled = true;
      server.externalDomain = "https://immich.net.scetrov.live";
    };
  };

  age.secrets = {
    immich_oidc_client_id = {
      file = /root/secrets/immich_oidc_client_id.age;
      mode = "0400";
    };
    immich_oidc_client_secret = {
      file = /root/secrets/immich_oidc_client_secret.age;
      mode = "0400";
    };
    immich_admin_email = {
      file = /root/secrets/immich_admin_email.age;
      mode = "0400";
    };
    immich_admin_password = {
      file = /root/secrets/immich_admin_password.age;
      mode = "0400";
    };
  };

  systemd.services.immich-server = {
    restartTriggers = [
      config.age.secrets.immich_oidc_client_id.file
      config.age.secrets.immich_oidc_client_secret.file
      config.age.secrets.immich_admin_email.file
      config.age.secrets.immich_admin_password.file
    ];
    serviceConfig = {
      LoadCredential = [
        "admin-email:${config.age.secrets.immich_admin_email.path}"
        "admin-password:${config.age.secrets.immich_admin_password.path}"
      ];
      ExecStartPost = "${pkgs.python3}/bin/python3 ${./immich-bootstrap.py}";
      TimeoutStartSec = 180;
      UMask = "0077";
    };
  };

  # On initial activation do not publish the new virtual host before local
  # administrator bootstrap has finished (ExecStartPost is part of startup).
  systemd.services.caddy.after = lib.mkIf config.services.immich.enable [ "immich-server.service" ];

  # Native application authentication also covers mobile, API and websocket
  # traffic: do not add a second proxy-authentication gate here.
  services.caddy = lib.mkIf config.services.immich.enable {
    enable = true;
    virtualHosts."immich.net.scetrov.live" = {
      useACMEHost = "scetrov.live";
      extraConfig = ''
        reverse_proxy 127.0.0.1:3000 {
          header_up X-Real-IP {remote_host}
        }
      '';
    };
  };
}
