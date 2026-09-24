{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.scetrov.services.project-zomboid;
  stateDir = "/var/lib/project-zomboid";
  steamDir = "${stateDir}/steam";
  profileDir = "${stateDir}/Zomboid";
  ini = "${profileDir}/Server/${cfg.serverName}.ini";
  workshopIds = lib.concatStringsSep ";" (map (mod: mod.workshopId) cfg.mods);
  workshopIdWords = lib.concatStringsSep " " (map (mod: mod.workshopId) cfg.mods);
  modIds = lib.concatStringsSep ";" (map (mod: "\\${mod.modId}") cfg.mods);
  initialise = pkgs.writeShellScript "project-zomboid-initialise" ''
    set -euo pipefail
    install -d -m 0750 ${steamDir} ${profileDir}/Server
    # Only reconcile the profile; the world, databases, logs and Workshop cache
    # remain game-owned and are never deleted or replaced here.
    if [ ! -e ${ini} ]; then
      umask 077
      join_password=$(cat ${cfg.joinPasswordFile})
      cat >${ini} <<EOF
    DefaultPort=${toString cfg.gamePort}
    UDPPort=${toString cfg.queryPort}
    Public=false
    Open=false
    MaxPlayers=${toString cfg.maxPlayers}
    RCONPort=0
    RCONPassword=
    Password=$join_password
    WorkshopItems=${workshopIds}
    Mods=${modIds}
    EOF
    fi

    # SandboxVars is game-owned mutable state. Reconcile only these explicit,
    # safe runtime values while the service is stopped; leave all other world
    # configuration and generated data untouched.
    sandbox=${profileDir}/Server/${cfg.serverName}_SandboxVars.lua
    if [ -f "$sandbox" ]; then
      set_sandbox_value() {
        key="$1"
        value="$2"
        if grep -q "^[[:space:]]*$key[[:space:]]*=" "$sandbox"; then
          ${pkgs.gnused}/bin/sed -i -E "s|^[[:space:]]*$key[[:space:]]*=.*|    $key = $value,|" "$sandbox"
        else
          ${pkgs.gnused}/bin/sed -i "/^SandboxVars = {/a\\    $key = $value," "$sandbox"
        fi
      }
      set_sandbox_value HoursForCorpseRemoval ${toString cfg.corpseRemovalHours}.0
      set_sandbox_value MaximumLooted ${toString cfg.maximumLootedBuildingChance}
      set_sandbox_value PopulationStartMultiplier ${toString cfg.zombiePopulationStartMultiplier}
      set_sandbox_value PopulationPeakMultiplier ${toString cfg.zombiePopulationPeakMultiplier}
      set_sandbox_value RedistributeHours ${toString cfg.zombieRedistributeHours}.0
      grep -q "^[[:space:]]*HoursForCorpseRemoval[[:space:]]*=[[:space:]]*${toString cfg.corpseRemovalHours}.0," "$sandbox"
      grep -q "^[[:space:]]*MaximumLooted[[:space:]]*=[[:space:]]*${toString cfg.maximumLootedBuildingChance}," "$sandbox"
      grep -q "^[[:space:]]*PopulationStartMultiplier[[:space:]]*=[[:space:]]*${toString cfg.zombiePopulationStartMultiplier}," "$sandbox"
      grep -q "^[[:space:]]*PopulationPeakMultiplier[[:space:]]*=[[:space:]]*${toString cfg.zombiePopulationPeakMultiplier}," "$sandbox"
      grep -q "^[[:space:]]*RedistributeHours[[:space:]]*=[[:space:]]*${toString cfg.zombieRedistributeHours}.0," "$sandbox"
    fi
  '';
  steamOpenSSLCompat = pkgs.runCommand "project-zomboid-steam-openssl" { } ''
    # buildFHSEnv mounts target packages at /usr, so `local` becomes
    # /usr/local inside SteamCMD's runtime (OpenSSL's compiled default).
    mkdir -p "$out/local/ssl"
    ln -s ${pkgs.openssl.out}/etc/ssl/openssl.cnf "$out/local/ssl/openssl.cnf"
    ln -s ${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt "$out/local/ssl/cert.pem"
    ln -s ${pkgs.cacert.hashed}/etc/ssl/certs "$out/local/ssl/certs"
  '';
  steamRuntime =
    (pkgs.steam.override {
      extraPkgs = _: [ steamOpenSSLCompat ];
      # SteamCMD runs as an unprivileged user; the host's /etc/static symlinks
      # become inaccessible inside steam-run, so bind real CA files directly.
      extraBwrapArgs = [
        "--tmpfs"
        "/etc/ssl"
        "--dir"
        "/etc/ssl/certs"
        "--ro-bind"
        "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
        "/etc/ssl/certs/ca-certificates.crt"
        "--ro-bind"
        "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
        "/etc/ssl/certs/ca-bundle.crt"
        "--ro-bind"
        "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
        "/etc/ssl/cert.pem"
      ];
      # Pass these through bubblewrap explicitly; inherited variables are not
      # reliable after SteamCMD drops privileges to the service account.
      extraEnv = {
        OPENSSL_CONF = "${pkgs.openssl.out}/etc/ssl/openssl.cnf";
        SSL_CERT_FILE = "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
        SSL_CERT_DIR = "${pkgs.cacert.hashed}/etc/ssl/certs";
      };
    }).run;
  steamcmd = pkgs.writeShellScript "project-zomboid-steamcmd" ''
    set -euo pipefail
    steam_root="$HOME/.local/share/Steam"
    if [ ! -e "$steam_root/steamcmd.sh" ]; then
      mkdir -p "$steam_root"/{appcache,config,logs,Steamapps/common,linux32}
      mkdir -p "$HOME/.steam"
      ln -sfn "$steam_root" "$HOME/.steam/root"
      ln -sfn "$steam_root" "$HOME/.steam/steam"
      (
        cd ${pkgs.steamcmd}/share/steamcmd
        find . -type f -exec install -Dm755 "{}" "$steam_root/{}" \;
      )
    fi
    exec ${steamRuntime}/bin/steam-run "$steam_root/steamcmd.sh" "$@"
  '';
  launch = pkgs.writeShellScript "project-zomboid-launch" ''
    set -euo pipefail
    fifo=${stateDir}/control/console.fifo
    rm -f "$fifo"
    mkfifo -m 0600 "$fifo"
    exec 3<>"$fifo"
    # The game stores the admin account in its database after first boot.
    # Bootstrap via the private console, never a process argument.
    if [ ! -e ${profileDir}/db/${cfg.serverName}.db ]; then
      admin_password=$(cat ${cfg.adminPasswordFile})
      printf '%s\n' "$admin_password" >&3
      unset admin_password
    fi
    exec ${pkgs.bash}/bin/bash ${steamDir}/start-server.sh -servername ${lib.escapeShellArg cfg.serverName} <&3
  '';
  stop = pkgs.writeShellScript "project-zomboid-stop" ''
    set -euo pipefail
    fifo=${stateDir}/control/console.fifo
    if [ -p "$fifo" ]; then
      printf 'save\n' >"$fifo"
      sleep 15
      printf 'quit\n' >"$fifo"
    fi
  '';
  maintenance = pkgs.writeShellScript "project-zomboid-maintenance" ''
    set -euo pipefail
    export PATH=${pkgs.coreutils}/bin:${pkgs.findutils}/bin:${pkgs.gnugrep}/bin:${pkgs.gnutar}/bin:${pkgs.gzip}/bin:${pkgs.util-linux}/bin:${pkgs.systemd}/bin
    lock=${stateDir}/locks/maintenance.lock
    export backup_dir=${stateDir}/backups
    mkdir -p "$backup_dir"
    exec flock -n "$lock" ${pkgs.bash}/bin/bash -c '
      set -euo pipefail
      operation="$1"
      backup() {
        stamp=$(date -u +%Y%m%dT%H%M%SZ)
        archive="$backup_dir/$stamp-$operation.tar.gz"
        test ! -e "$archive" || { echo "archive already exists: $archive" >&2; return 1; }
        tmp=$(mktemp "$backup_dir/.incomplete.XXXXXXXX")
        # Include Steam session and caches as well as the app and game state.
        if ! tar -C ${stateDir} --exclude=backups --exclude=locks --exclude=control -czf "$tmp" steam Zomboid .local .steam || ! tar -tzf "$tmp" >/dev/null; then
          rm -f -- "$tmp"
          return 1
        fi
        mv -- "$tmp" "$archive"
        echo "Recovery point: $archive"
        ls -1t "$backup_dir"/*.tar.gz 2>/dev/null | tail -n +$(( ${toString cfg.backupRetention} + 1 )) | xargs -r rm -f --
      }
      verify_workshop() {
        ${lib.concatMapStrings (mod: ''
          find ${steamDir}/steamapps/workshop/content/108600/${mod.workshopId} -name mod.info -exec grep -lqx 'id=${mod.modId}' {} + | grep -q .
        '') cfg.mods}
      }
      start_on_exit() { systemctl start project-zomboid.service; }
      case "$operation" in
        restart) systemctl restart project-zomboid.service ;;
        backup)
          systemctl stop project-zomboid.service
          trap start_on_exit EXIT
          backup
          trap - EXIT
          systemctl start project-zomboid.service
          ;;
        update)
          systemctl stop project-zomboid.service
          trap start_on_exit EXIT
          backup
          trap - EXIT
          # If validation fails, never launch a partly updated app or mod set.
          update_failure() { echo "Update failed; server remains stopped. Restore the recovery point above before restarting." >&2; }
          trap update_failure ERR
          run_steamcmd() {
            ${pkgs.util-linux}/bin/runuser -u ${cfg.user} -- ${pkgs.coreutils}/bin/env HOME=${stateDir} SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt SSL_CERT_DIR=${pkgs.cacert}/etc/ssl/certs ${lib.escapeShellArg cfg.steamcmdPath} "$@"
          }
          run_steamcmd +force_install_dir ${steamDir} +login ${lib.escapeShellArg cfg.steamAccount} +app_update 380870 validate +quit
          for item in ${workshopIdWords}; do run_steamcmd +force_install_dir ${steamDir} +login ${lib.escapeShellArg cfg.steamAccount} +workshop_download_item 108600 "$item" validate +quit; done
          verify_workshop
          systemctl start project-zomboid.service
          systemctl is-active --quiet project-zomboid.service
          trap - ERR
          ;;
        restore)
          archive="$2"
          case "$archive" in "$backup_dir"/*.tar.gz) ;; *) echo "restore archive must be beneath $backup_dir" >&2; exit 64;; esac
          test -f "$archive"
          # Validate and stage the archive before touching the live state.
          staging=$(mktemp -d ${stateDir}/.restore.XXXXXXXX)
          trap "rm -rf -- \"$staging\"" EXIT
          tar -C "$staging" -xzf "$archive"
          test -d "$staging/steam" && test -d "$staging/Zomboid"
          systemctl stop project-zomboid.service
          quarantine=${stateDir}/quarantine-$(date -u +%Y%m%dT%H%M%SZ)
          mkdir -p "$quarantine"
          for path in steam Zomboid .local .steam; do
            if [ -e "$staging/$path" ]; then
              test ! -e ${stateDir}/"$path" || mv ${stateDir}/"$path" "$quarantine"/
              mv "$staging/$path" ${stateDir}/
            fi
          done
          chown -R ${cfg.user}:${cfg.user} ${steamDir} ${profileDir}
          for path in .local .steam; do test ! -e ${stateDir}/"$path" || chown -R ${cfg.user}:${cfg.user} ${stateDir}/"$path"; done
          systemctl start project-zomboid.service
          ;;
        reconcile-profile)
          systemctl stop project-zomboid.service
          ${pkgs.util-linux}/bin/runuser -u ${cfg.user} -- ${initialise}
          systemctl start project-zomboid.service
          ;;
        reset-world)
          test "''${2-}" = --confirm || { echo "reset-world requires --confirm" >&2; exit 64; }
          systemctl stop project-zomboid.service
          trap start_on_exit EXIT
          backup
          quarantine=${stateDir}/quarantine-reset-$(date -u +%Y%m%dT%H%M%SZ)
          mkdir -p "$quarantine"
          test ! -e ${profileDir} || mv ${profileDir} "$quarantine"/
          ${initialise}
          chown -R ${cfg.user}:${cfg.user} ${profileDir}
          trap - EXIT
          systemctl start project-zomboid.service
          ;;
        *) echo "usage: project-zomboid-maintenance {restart|backup|update|restore ARCHIVE|reconcile-profile|reset-world --confirm}" >&2; exit 64 ;;
      esac
    ' bash "$@"
  '';
in
{
  options.scetrov.services.project-zomboid = {
    enable = lib.mkEnableOption "Project Zomboid Build 42 dedicated server";
    user = lib.mkOption {
      type = lib.types.str;
      default = "project-zomboid";
      readOnly = true;
    };
    serverName = lib.mkOption {
      type = lib.types.str;
      default = "pz-server";
    };
    gamePort = lib.mkOption {
      type = lib.types.port;
      default = 16261;
    };
    queryPort = lib.mkOption {
      type = lib.types.port;
      default = 16262;
    };
    lanCidrs = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ "10.229.0.0/16" ];
    };
    maxPlayers = lib.mkOption {
      type = lib.types.ints.between 1 32;
      default = 8;
    };
    memoryMax = lib.mkOption {
      type = lib.types.str;
      default = "4G";
    };
    steamAccount = lib.mkOption {
      type = lib.types.str;
      description = "Licensed dedicated Steam account whose persistent session is used only for maintenance.";
    };
    steamcmdPath = lib.mkOption {
      type = lib.types.str;
      default = "${steamcmd}";
      description = "SteamCMD executable with an OpenSSL-compatible Steam runtime.";
    };
    backupRetention = lib.mkOption {
      type = lib.types.ints.between 1 365;
      default = 7;
    };
    corpseRemovalHours = lib.mkOption {
      type = lib.types.ints.between 0 8760;
      default = 216;
      description = "In-game hours before zombie corpses are removed.";
    };
    maximumLootedBuildingChance = lib.mkOption {
      type = lib.types.ints.between 0 100;
      default = 25;
      description = "Maximum percentage chance that a newly discovered building is pre-looted.";
    };
    zombiePopulationStartMultiplier = lib.mkOption {
      type = lib.types.numbers.between 0.0 4.0;
      default = 1.0;
      description = "Zombie population multiplier at world start.";
    };
    zombiePopulationPeakMultiplier = lib.mkOption {
      type = lib.types.numbers.between 0.0 4.0;
      default = 1.5;
      description = "Zombie population multiplier at the configured peak day.";
    };
    zombieRedistributeHours = lib.mkOption {
      type = lib.types.ints.between 0 8760;
      default = 12;
      description = "In-game hours between same-cell zombie redistribution passes.";
    };
    adminPasswordFile = lib.mkOption { type = lib.types.path; };
    joinPasswordFile = lib.mkOption { type = lib.types.path; };
    enableHeadscaleAccess = lib.mkEnableOption "explicit Headscale gameplay access";
    headscaleInterface = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
    };
    headscaleCidrs = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
    };
    mods = lib.mkOption {
      type = lib.types.listOf (
        lib.types.submodule {
          options = {
            workshopId = lib.mkOption { type = lib.types.str; };
            modId = lib.mkOption { type = lib.types.str; };
          };
        }
      );
      default = [
        {
          workshopId = "3077900375";
          modId = "ChuckleberryFinnAlertSystem";
        }
        {
          workshopId = "2896041179";
          modId = "errorMagnifier";
        }
        {
          workshopId = "2503622437";
          modId = "SkillRecoveryJournal";
        }
      ];
    };
  };

  config = lib.mkIf cfg.enable {
    # SteamCMD's bundled OpenSSL needs both its legacy bundle path and the
    # OpenSSL-hashed certificates that the NixOS default CA directory omits.
    environment.etc = {
      "ssl/cert.pem".source = "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
    }
    // lib.mapAttrs' (name: _: {
      name = "ssl/certs/${name}";
      value.source = "${pkgs.cacert.hashed}/etc/ssl/certs/${name}";
    }) (builtins.readDir "${pkgs.cacert.hashed}/etc/ssl/certs");
    age.secrets.project_zomboid_admin_password = {
      file = /root/secrets/project_zomboid_admin_password.age;
      owner = cfg.user;
      group = cfg.user;
      mode = "0400";
    };
    age.secrets.project_zomboid_join_password = {
      file = /root/secrets/project_zomboid_join_password.age;
      owner = cfg.user;
      group = cfg.user;
      mode = "0400";
    };
    assertions = [
      {
        assertion =
          !cfg.enableHeadscaleAccess || (cfg.headscaleInterface != null && cfg.headscaleCidrs != [ ]);
        message = "Project Zomboid Headscale access requires an interface and source CIDRs.";
      }
    ];
    users.groups.${cfg.user} = { };
    users.users.${cfg.user} = {
      isSystemUser = true;
      group = cfg.user;
      home = stateDir;
      createHome = false;
    };
    systemd.tmpfiles.rules = [
      "d ${stateDir} 0750 ${cfg.user} ${cfg.user} - -"
      "d ${steamDir} 0750 ${cfg.user} ${cfg.user} - -"
      "d ${profileDir} 0750 ${cfg.user} ${cfg.user} - -"
      "d ${stateDir}/control 0700 ${cfg.user} ${cfg.user} - -"
      "d ${stateDir}/backups 0750 ${cfg.user} ${cfg.user} - -"
      "d ${stateDir}/locks 0700 ${cfg.user} ${cfg.user} - -"
    ];
    networking.firewall.extraCommands =
      lib.concatMapStrings (
        cidr:
        lib.concatMapStrings
          (port: "iptables -A nixos-fw -p udp -s ${cidr} --dport ${toString port} -j nixos-fw-accept\n")
          [
            cfg.gamePort
            cfg.queryPort
          ]
      ) cfg.lanCidrs
      + lib.optionalString cfg.enableHeadscaleAccess (
        lib.concatMapStrings (
          cidr:
          lib.concatMapStrings
            (
              port:
              "iptables -A nixos-fw -i ${cfg.headscaleInterface} -p udp -s ${cidr} --dport ${toString port} -j nixos-fw-accept\n"
            )
            [
              cfg.gamePort
              cfg.queryPort
            ]
        ) cfg.headscaleCidrs
      );
    networking.firewall.extraStopCommands =
      lib.concatMapStrings (
        cidr:
        lib.concatMapStrings
          (
            port:
            "iptables -D nixos-fw -p udp -s ${cidr} --dport ${toString port} -j nixos-fw-accept 2>/dev/null || true\n"
          )
          [
            cfg.gamePort
            cfg.queryPort
          ]
      ) cfg.lanCidrs
      + lib.optionalString cfg.enableHeadscaleAccess (
        lib.concatMapStrings (
          cidr:
          lib.concatMapStrings
            (
              port:
              "iptables -D nixos-fw -i ${cfg.headscaleInterface} -p udp -s ${cidr} --dport ${toString port} -j nixos-fw-accept 2>/dev/null || true\n"
            )
            [
              cfg.gamePort
              cfg.queryPort
            ]
        ) cfg.headscaleCidrs
      );
    environment.systemPackages = [
      (pkgs.writeShellScriptBin "project-zomboid-maintenance" ''exec ${maintenance} "$@"'')
    ];
    systemd.services.project-zomboid-backup = {
      description = "Create a Project Zomboid local recovery point";
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${maintenance} backup";
      };
    };
    systemd.timers.project-zomboid-backup = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "*-*-* 04:00:00";
        Persistent = true;
        Unit = "project-zomboid-backup.service";
      };
    };
    systemd.services.project-zomboid-restart = {
      description = "Gracefully restart Project Zomboid";
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${maintenance} restart";
      };
    };
    systemd.timers.project-zomboid-restart = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "Mon *-*-* 04:15:00";
        Persistent = true;
        Unit = "project-zomboid-restart.service";
      };
    };
    systemd.services.project-zomboid = {
      description = "Project Zomboid Build 42 dedicated server";
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
      wantedBy = [ "multi-user.target" ];
      serviceConfig = {
        User = cfg.user;
        Group = cfg.user;
        WorkingDirectory = steamDir;
        Environment = [
          "HOME=${stateDir}"
          "ZOMBOID_HOME=${profileDir}"
        ];
        ExecStartPre = initialise;
        ExecStart = launch;
        ExecStop = stop;
        Restart = "on-failure";
        RestartSec = "30s";
        MemoryMax = cfg.memoryMax;
        NoNewPrivileges = true;
        UMask = "0077";
        TimeoutStopSec = 120;
      };
      unitConfig = {
        ConditionPathExists = "${steamDir}/start-server.sh";
        StartLimitIntervalSec = 300;
        StartLimitBurst = 3;
      };
    };
  };
}
