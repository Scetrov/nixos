{ lib, pkgs, ... }:

let
  mutableScanDirectories = [
    "/home/scetrov"
  ];

  lowValueExclusions = [
    "^/var/lib/clamav(/|$)"
    "^/var/lib/containers(/|$)"
    "^/var/lib/loki(/|$)"
    "^/var/lib/tempo(/|$)"
    "^/var/lib/pyroscope(/|$)"
    "^/var/lib/frontier-indexer/timescaledb-data(/|$)"
    "^/var/lib/authentik/postgresql-data(/|$)"
    "^/var/lib/dependency-track/postgresql-data(/|$)"
  ];

  clamavDatabaseConditions = [
    "/var/lib/clamav/main.{c[vl]d,inc}"
    "/var/lib/clamav/daily.{c[vl]d,inc}"
  ];
in
{
  services.clamav = {
    daemon = {
      enable = true;
      settings = {
        LocalSocketMode = "660";
        ExtendedDetectionInfo = true;
        OfficialDatabaseOnly = true;
        AlertExceedsMax = true;
        ExcludePath = lowValueExclusions;
      };
    };

    updater = {
      enable = true;
      interval = "hourly";
      frequency = 12;
      settings = {
        NotifyClamd = "/etc/clamav/clamd.conf";
      };
    };

    scanner = {
      enable = true;
      interval = "*-*-* 03:15:00";
      scanDirectories = mutableScanDirectories;
    };
  };

  # Keep ClamAV on-access scanning disabled by default here. ClamAV's own
  # guidance recommends targeting specific ingress paths instead of trying to
  # watch the whole filesystem, which can cause unnecessary load or lockups.
  systemd.timers = {
    clamav-freshclam.timerConfig = {
      Persistent = true;
      RandomizedDelaySec = "15m";
    };

    clamdscan.timerConfig = {
      Persistent = true;
      RandomizedDelaySec = "45m";
    };
  };

  systemd.services = {
    clamav-daemon = {
      wants = lib.mkForce [ ];
      unitConfig.ConditionPathExistsGlob = clamavDatabaseConditions;
      serviceConfig = {
        Restart = "on-failure";
        RestartSec = "30s";
      };
    };

    clamav-freshclam.wants = [ "clamav-daemon.service" ];

    clamav-init-database = {
      description = "Bootstrap ClamAV signature database";
      wantedBy = [ "clamav-daemon.service" ];
      before = [ "clamav-daemon.service" ];
      unitConfig.ConditionPathExistsGlob = map (path: "!${path}") clamavDatabaseConditions;
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${pkgs.systemd}/bin/systemctl start clamav-freshclam.service";
      };
    };

    clamdscan.serviceConfig = {
      Nice = 10;
      IOSchedulingClass = "best-effort";
      IOSchedulingPriority = 7;
    };
  };
}
