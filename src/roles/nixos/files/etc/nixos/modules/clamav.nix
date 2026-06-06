{ lib, ... }:

let
  mutableScanDirectories = [
    "/etc"
    "/home"
    "/tmp"
    "/var/lib"
    "/var/tmp"
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
    clamav-daemon.serviceConfig = {
      Restart = "on-failure";
      RestartSec = "30s";
    };

    clamdscan.serviceConfig = {
      Nice = 10;
      IOSchedulingClass = "best-effort";
      IOSchedulingPriority = 7;
    };
  };
}
