{
  pkgs ? import <nixpkgs> { },
}:
let
  lib = pkgs.lib;
  evaluate =
    runnerEnabled: enabled: nftables:
    import <nixpkgs/nixos/lib/eval-config.nix> {
      system = "x86_64-linux";
      modules = [
        ../files/etc/nixos/modules/forgejo.nix
        ../files/etc/nixos/modules/local-networking.nix
        {
          # Evaluate without decrypting host secrets or importing live agenix.
          options.age.secrets = lib.mkOption {
            default = { };
            type = lib.types.attrsOf (
              lib.types.submodule (
                { name, ... }: {
                  options = {
                    file = lib.mkOption { type = lib.types.path; };
                    mode = lib.mkOption {
                      type = lib.types.str;
                      default = "0400";
                    };
                    path = lib.mkOption {
                      type = lib.types.str;
                      default = "/run/agenix/${name}";
                    };
                  };
                }
              )
            );
          };
          config = {
            system.stateVersion = "26.05";
            networking.hostName = "habiki";
            networking.nftables.enable = nftables;
            scetrov.services.forgejo.enable = enabled;
            scetrov.services.forgejo.runner.enable = lib.mkIf runnerEnabled true;
          };
        }
      ];
    };
  # Runner assertions/packet fixtures remain opt-in experimental regression tests.
  config = (evaluate true true false).config;
  disabled = (evaluate false false false).config;
  nft = (evaluate true true true).config;
  serviceOnly = (evaluate false true false).config;
  serviceOnlyNft = (evaluate false true true).config;
  settings = config.services.forgejo.settings;
  service = config.systemd.services.forgejo;
  site = config.services.caddy.virtualHosts."source.net.scetrov.live";
  privateSources = [
    "10.229.0.0/16"
    "100.64.0.0/10"
    "fd0b:281e:d657:3ca1::/64"
    "fd7a:115c:a1e0::/48"
  ];
in
assert lib.assertMsg
  (
    serviceOnly.services.forgejo.enable
    && !serviceOnly.services.forgejo.settings.actions.ENABLED
    && !serviceOnly.scetrov.services.forgejo.runner.enable
    && !(serviceOnly.users.users ? forgejo-runner)
    && !(serviceOnly.systemd.user.services ? forgejo-runner)
    && !(serviceOnly.systemd.user.services ? forgejo-runner-runtime)
    && !(serviceOnly.systemd.user.services ? forgejo-runner-cleanup)
    && !(serviceOnly.systemd.user.timers ? forgejo-runner-cleanup)
    && !(serviceOnly.systemd.services ? forgejo-runner-egress-ready)
    && !(lib.hasInfix "forgejo-job-egress" serviceOnly.networking.firewall.extraCommands)
    && !(lib.hasInfix "forgejo-job-egress" serviceOnly.networking.firewall.extraStopCommands)
    && !(serviceOnlyNft.networking.nftables.tables ? forgejo-job-egress)
    && !(lib.any (
      package: (package.name or "") == "forgejo-register-runner"
    ) serviceOnly.environment.systemPackages)
  )
  "private Forgejo must default to Actions disabled with no runner account, units, timer, registration or egress rules";
assert lib.assertMsg (
  config.services.forgejo.enable
  && config.services.forgejo.package == pkgs.forgejo
  && config.services.forgejo.database.type == "sqlite3"
  && config.services.forgejo.database.path == "/var/lib/forgejo/data/forgejo.db"
  && config.services.forgejo.repositoryRoot == "/var/lib/forgejo/repositories"
  && settings.server.HTTP_ADDR == "127.0.0.1"
  && settings.server.HTTP_PORT == 3002
  && settings.server.ROOT_URL == "https://source.net.scetrov.live/"
) "Forgejo must use persistent SQLite/state and a private HTTP listener";
assert lib.assertMsg (
  service.serviceConfig.User == "forgejo"
  && service.serviceConfig.ProtectSystem == "strict"
  && lib.hasInfix "/var/lib/forgejo" settings.server.SSH_SERVER_HOST_KEYS
  && settings.server.START_SSH_SERVER
  && settings.server.SSH_PORT == 2222
  && settings.server.SSH_LISTEN_PORT == 2222
  && settings.server.SSH_USER == "git"
) "built-in Git SSH identity must be separate and persistent";
assert lib.assertMsg (
  !(builtins.elem 2222 config.networking.firewall.allowedTCPPorts)
  && builtins.all (
    source: lib.hasInfix source config.networking.firewall.extraCommands
  ) privateSources
  && lib.hasInfix "ip6tables" config.networking.firewall.extraCommands
  && lib.hasInfix "--dport 2222" config.networking.firewall.extraStopCommands
  && !(lib.hasInfix "--dport 22 " config.networking.firewall.extraCommands)
  && builtins.all (source: lib.hasInfix source nft.networking.firewall.extraInputRules) privateSources
) "SSH firewall must be source-scoped on both backends and not alter admin SSH";
assert lib.assertMsg (
  site.useACMEHost == "scetrov.live"
  && builtins.all (source: lib.hasInfix source site.extraConfig) privateSources
  && lib.hasInfix "not remote_ip" site.extraConfig
  && lib.hasInfix "respond @internal" site.extraConfig
  && lib.hasInfix "/metrics" site.extraConfig
  && lib.hasInfix "/api/internal/*" site.extraConfig
  && !(lib.hasInfix "forward_auth " site.extraConfig)
  && settings.security.REVERSE_PROXY_TRUSTED_PROXIES == "127.0.0.1/32"
) "Caddy must restrict private peers and internal routes without forward auth";
assert lib.assertMsg (
  settings.service.DISABLE_REGISTRATION
  && settings.service.REQUIRE_SIGNIN_VIEW
  && !settings.service.ENABLE_BASIC_AUTHENTICATION
  && !settings.service.ENABLE_INTERNAL_SIGNIN
  && settings.repository.FORCE_PRIVATE
  && settings.oauth2_client.ENABLE_AUTO_REGISTRATION
  && settings.oauth2_client.ACCOUNT_LINKING == "disabled"
  && !settings.openid.ENABLE_OPENID_SIGNIN
  && !settings.openid.ENABLE_OPENID_SIGNUP
  && builtins.elem "forgejo_oidc_client_secret:/run/agenix/forgejo_oidc_client_secret" service.serviceConfig.LoadCredential
  && lib.hasInfix "forgejo-reconcile.py" service.preStart
  && builtins.length service.restartTriggers >= 2
) "registration, anonymous repositories, and password Basic auth must be disabled";
assert lib.assertMsg
  (
    config.users.users.forgejo-runner.isSystemUser
    && config.users.users.forgejo-runner.linger
    && config.users.users.forgejo-runner.autoSubUidGidRange
    && config.users.users.forgejo-runner.extraGroups == [ ]
    && config.users.users.forgejo-runner.home == "/var/lib/forgejo-runner"
    && config.users.users.forgejo-runner.homeMode == "0700"
    && config.systemd.user.services.forgejo-runner-runtime.unitConfig.ConditionUser == "forgejo-runner"
    && config.systemd.user.services.forgejo-runner-runtime.serviceConfig.Delegate
    && lib.hasInfix "--cgroup-manager=systemd" config.systemd.user.services.forgejo-runner-runtime.serviceConfig.ExecStart
    &&
      config.systemd.user.services.forgejo-runner-runtime.environment.DBUS_SESSION_BUS_ADDRESS
      == "unix:path=%t/bus"
    && lib.hasInfix "--root /var/lib/forgejo-runner/runtime/storage" config.systemd.user.services.forgejo-runner-runtime.serviceConfig.ExecStart
    &&
      config.systemd.user.services.forgejo-runner.environment.DOCKER_HOST
      == "unix://%t/forgejo-runner-runtime/podman.sock"
    &&
      config.systemd.user.services.forgejo-runner.unitConfig.ConditionPathExists
      == "/var/lib/forgejo-runner-control/config.yaml"
    && builtins.elem "forgejo-runner-runtime.service" config.systemd.user.services.forgejo-runner.requires
    && builtins.elem "forgejo-runner.service" config.systemd.user.services.forgejo-runner-cleanup.conflicts
    && builtins.elem "forgejo-runner.service" config.systemd.user.services.forgejo-runner-cleanup.before
    &&
      config.systemd.user.services.forgejo-runner-cleanup.unitConfig.OnSuccess == "forgejo-runner.service"
    && config.systemd.user.services.forgejo-runner-cleanup.unitConfig.ConditionUser == "forgejo-runner"
    && config.systemd.user.timers.forgejo-runner-cleanup.timerConfig.Persistent
    && builtins.length config.systemd.user.services.forgejo-runner.serviceConfig.ExecStartPre == 2
    && !(disabled.systemd.user.services ? forgejo-runner-cleanup)
    && !(disabled.systemd.user.timers ? forgejo-runner-cleanup)
    && !(disabled.systemd.user.services ? forgejo-runner)
    && !(disabled.systemd.user.services ? forgejo-runner-runtime)
  )
  "runner must use its own unprivileged lingering account/runtime and fail closed before registration";
assert lib.assertMsg (
  lib.hasInfix "--uid-owner forgejo-runner" config.networking.firewall.extraCommands
  && lib.hasInfix "-d 10.229.10.2 --dport 443 -j RETURN" config.networking.firewall.extraCommands
  && lib.hasInfix "-d 127.0.0.0/8 -j REJECT" config.networking.firewall.extraCommands
  && lib.hasInfix "-d fc00::/7 -j REJECT" config.networking.firewall.extraCommands
  && lib.hasInfix "--uid-owner forgejo-runner" config.networking.firewall.extraStopCommands
  && lib.hasInfix "meta skuid \"forgejo-runner\"" nft.networking.nftables.tables.forgejo-job-egress.content
  && !(disabled.networking.nftables.tables ? forgejo-job-egress)
  && !(lib.hasInfix "forgejo-job-egress" disabled.networking.firewall.extraCommands)
) "job egress must be user-scoped, private-destination restricted and removable";
assert lib.assertMsg (
  !disabled.services.forgejo.enable
  && !(disabled.systemd.services ? forgejo)
  && !(disabled.services.caddy.virtualHosts ? "source.net.scetrov.live")
  && !(lib.hasInfix "--dport 2222" disabled.networking.firewall.extraCommands)
  && builtins.elem "source.net.scetrov.live" config.networking.hosts."10.229.10.2"
) "disable must remove service and access rules; shared DNS must retain the alias";
{
  passed = true;
  caddyConfig = site.extraConfig;
  version = config.services.forgejo.package.version;
  egressStart = config.networking.firewall.extraCommands;
  egressStop = config.networking.firewall.extraStopCommands;
  egressNft = nft.networking.nftables.tables.forgejo-job-egress.content;
}
