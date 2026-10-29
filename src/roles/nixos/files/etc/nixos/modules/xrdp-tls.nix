{
  config,
  lib,
  pkgs,
  ...
}:
let
  tlsDir = "/var/lib/xrdp-tls";
  ca = config.age.secrets.xrdp_ca_cert.path;
  caKey = config.age.secrets.xrdp_ca_key.path;
  knownHosts = pkgs.writeText "xrdp-crl-known-hosts" ''
    10.229.10.2 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJ6Gw0SitGQ9Z2WcxD/KyS142YlBZYg6aFeYymRIdMFR
  '';
  prepare = pkgs.writeShellScript "xrdp-tls-renew" ''
    set -euo pipefail
    if ! result="$(${pkgs.python3}/bin/python3 ${./xrdp-tls-renew.py} renew \
      --target ${tlsDir} --state /var/lib/xrdp-ca --ca ${ca} --ca-key ${caKey} \
      --openssl ${pkgs.openssl}/bin/openssl --group xrdp \
      --sftp ${pkgs.openssh}/bin/sftp --identity "$CREDENTIALS_DIRECTORY/publisher-key" \
      --known-hosts ${knownHosts} --trust-bundle ${config.security.pki.caBundle})"; then
      echo "$result" >&2
      exit 1
    fi
    echo "$result"
    # Never restart sesman (which owns existing desktop sessions). Queue the
    # listener restart so it cannot deadlock on this required startup unit.
    if [ "$result" = renewed ] && ${pkgs.systemd}/bin/systemctl is-active --quiet xrdp.service; then
      ${pkgs.systemd}/bin/systemctl --no-block try-restart xrdp.service
    fi
  '';
in
{
  # This module is imported only on Bullit: the CA signing key is root-only,
  # not readable by the network-facing xrdp user or other managed hosts.
  age.secrets.xrdp_ca_cert.file = /root/secrets/xrdp_ca_cert.age;
  age.secrets.xrdp_ca_key.file = /root/secrets/xrdp_ca_key.age;
  age.secrets.xrdp_crl_publisher_key.file = /root/secrets/xrdp_crl_publisher_key.age;

  # Only an explicit initialization/recovery operation creates issuance records.
  systemd.tmpfiles.rules = [ "d /var/lib/xrdp-ca 0700 root root -" ];

  services.xrdp = {
    sslCert = "${tlsDir}/current/cert.pem";
    sslKey = "${tlsDir}/current/key.pem";
    extraConfDirCommands = ''
      substituteInPlace $out/xrdp.ini \
        --replace-fail 'security_layer=negotiate' 'security_layer=tls'
    '';
  };

  systemd.services.xrdp-tls-renew = {
    description = "Renew Bullit XRDP TLS certificate from its private CA";
    # Agenix on this host runs in activation before systemd starts units;
    # there is no agenix.service. These ordering-only edges also cover the
    # agenix sysusers backend without requiring nonexistent units.
    after = [
      "agenix-install-secrets.service"
      "agenix-chown.service"
      "network-online.target"
    ];
    wants = [ "network-online.target" ];
    before = [ "xrdp.service" ];
    restartTriggers = [
      config.age.secrets.xrdp_ca_cert.file
      config.age.secrets.xrdp_ca_key.file
      config.age.secrets.xrdp_crl_publisher_key.file
    ];
    serviceConfig = {
      Type = "oneshot";
      ExecStart = prepare;
      User = "root";
      LoadCredential = [ "publisher-key:${config.age.secrets.xrdp_crl_publisher_key.path}" ];
      ReadWritePaths = [ "/var/lib/xrdp-ca" ];
      TimeoutStartSec = "180s";
      # systemd reapplies StateDirectory ownership on every invocation,
      # including no-op renewals. Keep directory traversal available to xrdp.
      Group = "xrdp";
      StateDirectory = "xrdp-tls";
      StateDirectoryMode = "0750";
      UMask = "0077";
      ProtectSystem = "strict";
      ProtectHome = true;
      PrivateTmp = true;
      NoNewPrivileges = true;
    };
  };

  systemd.timers.xrdp-tls-renew = {
    wantedBy = [ "timers.target" ];
    timerConfig = {
      OnCalendar = "daily";
      Persistent = true;
      RandomizedDelaySec = "1h";
    };
  };

  systemd.services.xrdp = {
    after = [ "xrdp-tls-renew.service" ];
    requires = [ "xrdp-tls-renew.service" ];
    # Replace upstream's preStart, which silently generates a self-signed cert
    # if files are missing. Retain its socket setup and legacy RSA-key setup.
    preStart = lib.mkForce ''
      test -s ${tlsDir}/current/cert.pem
      test -s ${tlsDir}/current/key.pem
      mkdir -p /tmp/.xrdp
      chown xrdp:xrdp /tmp/.xrdp
      chmod 3777 /tmp/.xrdp
      if [ ! -s /run/xrdp/rsakeys.ini ]; then
        mkdir -p /run/xrdp
        ${config.services.xrdp.package}/bin/xrdp-keygen xrdp /run/xrdp/rsakeys.ini
      fi
    '';
  };
}
