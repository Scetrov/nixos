# Habiki publishes public revocation data; it never holds the CA signing key.
{ pkgs, ... }:
{
  users.groups.xrdp-crl-publisher = { };
  users.groups.xrdp-crl-monitor = { };
  users.users.xrdp-crl-monitor = {
    isSystemUser = true;
    group = "xrdp-crl-monitor";
    extraGroups = [ "xrdp-crl-publisher" ];
  };
  users.users.xrdp-crl-publisher = {
    isSystemUser = true;
    group = "xrdp-crl-publisher";
    home = "/var/lib/xrdp-crl";
    createHome = false;
    shell = pkgs.bash;
    openssh.authorizedKeys.keys = [
      ''restrict,from="10.229.10.10" ${builtins.readFile ./xrdp-crl-publisher.pub}''
    ];
  };
  services.openssh.settings.AllowUsers = [ "xrdp-crl-publisher" ];
  services.openssh.extraConfig = ''
    Match User xrdp-crl-publisher
      ChrootDirectory /var/lib/xrdp-crl
      ForceCommand internal-sftp -d /upload -u 0022
      AuthenticationMethods publickey
      PasswordAuthentication no
      KbdInteractiveAuthentication no
      DisableForwarding yes
      AllowTcpForwarding no
      X11Forwarding no
      PermitTTY no
    Match all
  '';
  systemd.tmpfiles.rules = [
    "d /var/lib/xrdp-crl 0755 root root -"
    "d /var/lib/xrdp-crl/upload 0755 xrdp-crl-publisher xrdp-crl-publisher -"
    "d /var/lib/xrdp-crl-metrics 0755 xrdp-crl-monitor xrdp-crl-monitor -"
  ];

  services.caddy.virtualHosts."https://crl.net.scetrov.live" = {
    useACMEHost = "scetrov.live";
    logFormat = ''
      output stderr
      format json
    '';
    extraConfig = ''
      route {
        @notLocal not remote_ip 10.229.0.0/16 127.0.0.1 ::1
        respond @notLocal "Forbidden" 403
        @crl {
          path /bullit-xrdp.crl
          method GET HEAD
        }
        handle @crl {
          root * /var/lib/xrdp-crl/upload
          header Content-Type application/pkix-crl
          header Cache-Control "public, max-age=300"
          file_server
        }
        respond "Not Found" 404
      }
    '';
  };
  services.caddy.virtualHosts."http://crl.net.scetrov.live".extraConfig = ''
    respond "Not Found" 404
  '';

  systemd.services.xrdp-crl-monitor = {
    description = "Check published XRDP CRL signature, expiry and ledger backup freshness";
    # First deployment must configure the receiver before Bullit can upload.
    # Missing data after commissioning is covered by the HTTPS/absent/stale alerts.
    unitConfig.ConditionPathExists = "/var/lib/xrdp-crl/upload/bullit-xrdp.crl";
    serviceConfig = {
      Type = "oneshot";
      User = "xrdp-crl-monitor";
      Group = "xrdp-crl-monitor";
      ExecStart = "${pkgs.python3}/bin/python3 ${./xrdp-crl-monitor.py} --openssl ${pkgs.openssl}/bin/openssl --ssh-keygen ${pkgs.openssh}/bin/ssh-keygen --publisher-public-key ${./xrdp-crl-publisher.pub}";
      ProtectSystem = "strict";
      ReadWritePaths = [ "/var/lib/xrdp-crl-metrics" ];
      ProtectHome = true;
      PrivateTmp = true;
      NoNewPrivileges = true;
      UMask = "0022";
    };
  };
  systemd.timers.xrdp-crl-monitor = {
    wantedBy = [ "timers.target" ];
    timerConfig = {
      OnBootSec = "2min";
      OnUnitActiveSec = "5min";
    };
  };
}
