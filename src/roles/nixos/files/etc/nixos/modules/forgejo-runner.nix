{
  config,
  lib,
  pkgs,
  ...
}:

let
  enabled = config.scetrov.services.forgejo.runner.enable;
  home = "/var/lib/forgejo-runner";
  runtimeDir = "${home}/runtime";
  controlDir = "/var/lib/forgejo-runner-control";
  # Shared with the actual daemon-mode job fixture. No credentials here;
  # execution labels stay empty until the acceptance image is selected.
  template = ./forgejo-runner-config.json;
  registerRunner = pkgs.writeShellApplication {
    name = "forgejo-register-runner";
    text = ''
      set +x
      exec ${lib.getExe pkgs.python3} ${./forgejo-runner-register.py} \
        --binary ${lib.getExe config.services.forgejo.package} \
        --server-config ${config.services.forgejo.customDir}/conf/app.ini \
        --work-path ${config.services.forgejo.stateDir} \
        --template ${template} \
        --instance https://source.net.scetrov.live/ "$@"
    '';
  };
  transientDir = "${home}/transient";
  podman = lib.getExe config.virtualisation.podman.package;
  userOnly = {
    ConditionUser = "forgejo-runner";
  };
  dnsServers = [
    "10.229.53.1"
    "10.229.53.2"
  ];
  blockedIPv4 = [
    "0.0.0.0/8"
    "10.0.0.0/8"
    "100.64.0.0/10"
    "127.0.0.0/8"
    "169.254.0.0/16"
    "172.16.0.0/12"
    "192.168.0.0/16"
    "198.18.0.0/15"
    "224.0.0.0/4"
    "240.0.0.0/4"
  ];
  blockedIPv6 = [
    "::/128"
    "::1/128"
    "fc00::/7"
    "fe80::/10"
    "ff00::/8"
  ];
  egressRules =
    family: blocked:
    lib.optional (family == "iptables") "-p tcp -d 10.229.10.2 --dport 443 -j RETURN"
    ++ lib.optionals (family == "iptables") (
      lib.concatMap (dns: [
        "-p udp -d ${dns} --dport 53 -j RETURN"
        "-p tcp -d ${dns} --dport 53 -j RETURN"
      ]) dnsServers
    )
    ++ map (destination: "-d ${destination} -j REJECT") blocked
    ++ [
      "-p tcp -m multiport --dports 80,443 -j RETURN"
      "-j REJECT"
    ];
  egressStart =
    lib.concatMapStringsSep "\n"
      (
        family:
        let
          blocked = if family == "iptables" then blockedIPv4 else blockedIPv6;
        in
        ''
          ${family} -N forgejo-job-egress 2>/dev/null || true
          ${family} -F forgejo-job-egress
          ${lib.concatMapStringsSep "\n" (rule: "${family} -A forgejo-job-egress ${rule}") (
            egressRules family blocked
          )}
          ${family} -C OUTPUT -m owner --uid-owner forgejo-runner -j forgejo-job-egress 2>/dev/null || \
            ${family} -I OUTPUT 1 -m owner --uid-owner forgejo-runner -j forgejo-job-egress
        ''
      )
      [
        "iptables"
        "ip6tables"
      ];
  egressStop =
    lib.concatMapStringsSep "\n"
      (family: ''
        ${family} -D OUTPUT -m owner --uid-owner forgejo-runner -j forgejo-job-egress 2>/dev/null || true
        ${family} -F forgejo-job-egress 2>/dev/null || true
        ${family} -X forgejo-job-egress 2>/dev/null || true
      '')
      [
        "iptables"
        "ip6tables"
      ];
  firewallUnit = if config.networking.nftables.enable then "nftables.service" else "firewall.service";
  egressNft = ''
    chain runner-egress {
      ip daddr 10.229.10.2 tcp dport 443 return
      ip daddr { ${lib.concatStringsSep ", " dnsServers} } udp dport 53 return
      ip daddr { ${lib.concatStringsSep ", " dnsServers} } tcp dport 53 return
      ip daddr { ${lib.concatStringsSep ", " blockedIPv4} } reject
      ip6 daddr { ${lib.concatStringsSep ", " blockedIPv6} } reject
      tcp dport { 80, 443 } return
      reject
    }
    chain output {
      type filter hook output priority -10; policy accept;
      meta skuid "forgejo-runner" jump runner-egress
    }
  '';
  cleanup = pkgs.writeShellScript "forgejo-runner-cleanup" ''
    set -eu
    # A crashed daemon may leave job containers alive. Do not remove storage
    # while they can still use it; require deliberate runtime recovery instead.
    active=$(${podman} --cgroup-manager=systemd --root ${runtimeDir}/storage \
      --runroot "$XDG_RUNTIME_DIR/forgejo-runner-runtime/containers" ps -q)
    if [ -n "$active" ]; then
      echo "Runner containers remain active; refusing transient cleanup" >&2
      exit 1
    fi
    exec ${lib.getExe pkgs.python3} ${./forgejo-runner-cleanup.py} \
      --transient-dir ${transientDir}
  '';
in
{
  # Deferred experimental code, not part of the private-forge deployment.
  options.scetrov.services.forgejo.runner.enable =
    lib.mkEnableOption "experimental Forgejo Actions runner (not accepted for deployment)";

  config = lib.mkIf enabled {
    assertions = [
      {
        assertion = config.scetrov.services.forgejo.enable;
        message = "Forgejo runner requires the Forgejo service.";
      }
      {
        assertion = config.networking.firewall.enable;
        message = "Forgejo runner requires the host firewall for scoped egress restrictions.";
      }
    ];
    virtualisation.podman.enable = true;
    # User-manager ordering cannot depend directly on system-manager units.
    # Publish a root-owned readiness marker only after the host rules are loaded.
    systemd.services.forgejo-runner-egress-ready = {
      description = "Confirm Forgejo runner host egress policy is loaded";
      wantedBy = [ "multi-user.target" ];
      after = [ firewallUnit ];
      requires = [ firewallUnit ];
      partOf = [ firewallUnit ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        RuntimeDirectory = "forgejo-runner-egress";
        RuntimeDirectoryMode = "0755";
        ExecStart = "${pkgs.coreutils}/bin/touch /run/forgejo-runner-egress/ready";
        ExecStop = "${pkgs.coreutils}/bin/rm -f /run/forgejo-runner-egress/ready";
      };
    };
    # Rootless pasta/aardvark connections are owned by the dedicated host user.
    # Apply policy there, outside the job's namespace/capability boundary. Public
    # HTTP(S), Blocky DNS and Forgejo HTTPS only. The accepted residual risk is
    # other Caddy hostnames sharing Habiki:443; this is not a hostname ACL.
    networking.firewall = lib.mkIf (!config.networking.nftables.enable) {
      extraCommands = egressStart;
      extraStopCommands = egressStop;
    };
    networking.nftables.tables.forgejo-job-egress = lib.mkIf config.networking.nftables.enable {
      family = "inet";
      content = egressNft;
    };
    environment.systemPackages = [ registerRunner ];
    users.groups.forgejo-runner = { };
    users.users.forgejo-runner = {
      isSystemUser = true;
      group = "forgejo-runner";
      inherit home;
      createHome = true;
      homeMode = "0700";
      autoSubUidGidRange = true;
      linger = true;
      shell = "${pkgs.shadow}/bin/nologin";
    };
    systemd.tmpfiles.rules = [
      "d ${home} 0700 forgejo-runner forgejo-runner -"
      "d ${runtimeDir} 0700 forgejo-runner forgejo-runner -"
      # Root-owned sibling directory: the runner cannot replace its registration
      # directory/config or trick privileged deployment into following symlinks.
      "d ${controlDir} 0750 root forgejo-runner -"
      "d ${transientDir} 0700 forgejo-runner forgejo-runner -"
      "d ${transientDir}/workspace 0700 forgejo-runner forgejo-runner -"
      "d ${transientDir}/cache 0700 forgejo-runner forgejo-runner -"
    ];

    # A lingering dedicated user manager supplies the rootless runtime's user
    # bus and delegated cgroups. Never use Habiki's rootful Podman endpoint.
    # User units are installed globally, but ConditionUser excludes all other
    # accounts. The socket is private to this user's /run/user/<uid>.
    systemd.user.services.forgejo-runner-runtime = {
      description = "Dedicated rootless Forgejo job runtime";
      wantedBy = [ "default.target" ];
      unitConfig = userOnly;
      path = [
        pkgs.podman
        pkgs.coreutils
        pkgs.fuse-overlayfs
      ];
      environment = {
        DBUS_SESSION_BUS_ADDRESS = "unix:path=%t/bus";
        PATH = lib.mkForce "/run/wrappers/bin:${
          lib.makeBinPath [
            pkgs.podman
            pkgs.coreutils
            pkgs.fuse-overlayfs
          ]
        }";
      };
      serviceConfig = {
        Type = "exec";
        ExecStart = "${podman} --cgroup-manager=systemd --root ${runtimeDir}/storage --runroot %t/forgejo-runner-runtime/containers system service --time=0 unix://%t/forgejo-runner-runtime/podman.sock";
        Restart = "on-failure";
        RestartSec = 5;
        Delegate = true;
        RuntimeDirectory = "forgejo-runner-runtime";
        RuntimeDirectoryMode = "0700";
        UMask = "0077";
        # newuidmap/newgidmap need the NixOS setuid wrappers. Do not set
        # NoNewPrivileges or hide /run/wrappers on this runtime service.
        KillMode = "mixed";
        TimeoutStopSec = 60;
      };
    };

    # Weekly maintenance stops the daemon gracefully before deleting workspaces.
    # Cache is disabled; runtime image storage and registration are never pruned.
    systemd.user.timers.forgejo-runner-cleanup = {
      wantedBy = [ "timers.target" ];
      unitConfig = userOnly;
      timerConfig = {
        OnCalendar = "Sun *-*-* 04:00:00";
        Persistent = true;
        RandomizedDelaySec = "15m";
      };
    };
    systemd.user.services.forgejo-runner-cleanup = {
      description = "Clean dedicated Forgejo runner transient storage";
      unitConfig = userOnly // {
        OnSuccess = "forgejo-runner.service";
      };
      conflicts = [ "forgejo-runner.service" ];
      before = [ "forgejo-runner.service" ];
      after = [ "forgejo-runner-runtime.service" ];
      requires = [ "forgejo-runner-runtime.service" ];
      environment = {
        DBUS_SESSION_BUS_ADDRESS = "unix:path=%t/bus";
        PATH = config.systemd.user.services.forgejo-runner-runtime.environment.PATH;
      };
      serviceConfig = {
        Type = "oneshot";
        ExecStart = cleanup;
        UMask = "0077";
      };
    };

    systemd.user.services.forgejo-runner = {
      description = "Forgejo trusted-owner Actions runner";
      wantedBy = [ "default.target" ];
      after = [ "forgejo-runner-runtime.service" ];
      requires = [ "forgejo-runner-runtime.service" ];
      unitConfig = userOnly // {
        # Registration task writes protected connection config only after the
        # first-login gate. No job daemon starts with missing prerequisites.
        ConditionPathExists = "${controlDir}/config.yaml";
      };
      environment = {
        DOCKER_HOST = "unix://%t/forgejo-runner-runtime/podman.sock";
        DBUS_SESSION_BUS_ADDRESS = "unix:path=%t/bus";
        PATH = config.systemd.user.services.forgejo-runner-runtime.environment.PATH;
      };
      serviceConfig = {
        Type = "simple";
        ExecStartPre = [
          (pkgs.writeShellScript "forgejo-runtime-ready" ''
            for attempt in $(${pkgs.coreutils}/bin/seq 1 30); do
              if [ -f /run/forgejo-runner-egress/ready ] && \
                ${pkgs.curl}/bin/curl --silent --fail --max-time 2 \
                --unix-socket "$XDG_RUNTIME_DIR/forgejo-runner-runtime/podman.sock" \
                http://localhost/_ping >/dev/null; then
                exit 0
              fi
              ${pkgs.coreutils}/bin/sleep 1
            done
            echo "Dedicated Forgejo runtime is not ready" >&2
            exit 1
          '')
          cleanup
        ];
        ExecStart = "${lib.getExe pkgs.forgejo-runner} --config ${controlDir}/config.yaml daemon";
        WorkingDirectory = "${transientDir}/workspace";
        Restart = "on-failure";
        RestartSec = 5;
        UMask = "0077";
        NoNewPrivileges = true;
        TimeoutStopSec = 180;
      };
    };
  };
}
