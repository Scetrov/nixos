{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.scetrov.services.forgejo;
  privateIPv4 = [
    "10.229.0.0/16"
    "100.64.0.0/10"
  ];
  privateIPv6 = [
    "fd0b:281e:d657:3ca1::/64"
    "fd7a:115c:a1e0::/48"
  ];
  sshRules =
    lib.concatMap (source: [
      {
        tool = "iptables";
        inherit source;
      }
    ]) privateIPv4
    ++ lib.concatMap (source: [
      {
        tool = "ip6tables";
        inherit source;
      }
    ]) privateIPv6;
in
{
  imports = [ ./forgejo-runner.nix ];

  options.scetrov.services.forgejo.enable = lib.mkEnableOption "private Forgejo on Habiki";

  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = config.networking.hostName == "habiki";
        message = "The private Forgejo service is only supported on Habiki.";
      }
      {
        assertion = !(builtins.elem 2222 config.networking.firewall.allowedTCPPorts);
        message = "Forgejo SSH must not be opened globally via allowedTCPPorts.";
      }
    ];

    age.secrets.forgejo_oidc_client_id = {
      file = /root/secrets/forgejo_oidc_client_id.age;
      mode = "0400";
    };
    age.secrets.forgejo_oidc_client_secret = {
      file = /root/secrets/forgejo_oidc_client_secret.age;
      mode = "0400";
    };
    # Prometheus reads this file directly as its bearer token for /metrics,
    # so it must stay readable by the prometheus group.
    age.secrets.forgejo_metrics_token = {
      file = /root/secrets/forgejo_metrics_token.age;
      owner = "root";
      group = "prometheus";
      mode = "0440";
    };

    # Run after upstream config rendering/migrations, before the web process
    # loads authentication sources. Rotation restarts and reconciles in one run.
    systemd.services.forgejo = {
      restartTriggers = [
        config.age.secrets.forgejo_oidc_client_id.file
        config.age.secrets.forgejo_oidc_client_secret.file
      ];
      serviceConfig.LoadCredential = [
        "forgejo_oidc_client_id:${config.age.secrets.forgejo_oidc_client_id.path}"
        "forgejo_oidc_client_secret:${config.age.secrets.forgejo_oidc_client_secret.path}"
      ];
      preStart = lib.mkAfter ''
        set +x
        ${lib.getExe pkgs.python3} ${./forgejo-reconcile.py} \
          --binary ${lib.getExe config.services.forgejo.package} \
          --config ${config.services.forgejo.customDir}/conf/app.ini \
          --work-path ${config.services.forgejo.stateDir} \
          --discovery-url https://identity.net.scetrov.live/application/o/forgejo/.well-known/openid-configuration
      '';
    };

    services.forgejo = {
      enable = true;
      package = pkgs.forgejo;
      # The module feeds this path to Forgejo as the metrics.TOKEN credential;
      # the same file is Prometheus' bearer_token_file for the private scrape.
      secrets.metrics.TOKEN = config.age.secrets.forgejo_metrics_token.path;
      database.type = "sqlite3";
      stateDir = "/var/lib/forgejo";
      repositoryRoot = "/var/lib/forgejo/repositories";
      dump.enable = false; # No formal backup guarantee; snapshots are operator-managed.
      settings = {
        DEFAULT.APP_NAME = "Private Forgejo";
        server = {
          DOMAIN = "source.net.scetrov.live";
          ROOT_URL = "https://source.net.scetrov.live/";
          HTTP_ADDR = "127.0.0.1";
          HTTP_PORT = 3002;
          DISABLE_SSH = false;
          START_SSH_SERVER = true;
          SSH_DOMAIN = "source.net.scetrov.live";
          SSH_PORT = 2222;
          SSH_LISTEN_PORT = 2222;
          SSH_LISTEN_HOST = "::";
          BUILTIN_SSH_SERVER_USER = "git";
          SSH_USER = "git";
          # Forgejo generates a persistent RSA-4096 pair on first startup.
          SSH_SERVER_HOST_KEYS = "/var/lib/forgejo/data/ssh/forgejo.rsa";
        };
        repository = {
          DEFAULT_PRIVATE = "private";
          FORCE_PRIVATE = true;
        };
        service = {
          DISABLE_REGISTRATION = true;
          REQUIRE_SIGNIN_VIEW = true;
          ENABLE_INTERNAL_SIGNIN = false;
          ENABLE_BASIC_AUTHENTICATION = false; # Tokens still work; passwords do not.
          ENABLE_REVERSE_PROXY_AUTHENTICATION = false;
          ENABLE_REVERSE_PROXY_AUTHENTICATION_API = false;
        };
        security = {
          REVERSE_PROXY_LIMIT = 1;
          REVERSE_PROXY_TRUSTED_PROXIES = "127.0.0.1/32";
        };
        # Token-protected metrics on the same loopback listener; Caddy
        # denies /metrics through the virtual host, Prometheus scrapes
        # 127.0.0.1:3002 directly with the bearer token file.
        metrics = {
          ENABLED = true;
        };
        # OIDC auto-enrollment is separate from closed local registration in
        # v16. Administration derives from signed groups, never email matching.
        oauth2_client = {
          ENABLE_AUTO_REGISTRATION = true;
          USERNAME = "nickname";
          ACCOUNT_LINKING = "disabled";
          REGISTER_EMAIL_CONFIRM = false;
        };
        openid = {
          ENABLE_OPENID_SIGNIN = false;
          ENABLE_OPENID_SIGNUP = false;
        };
        session.COOKIE_SECURE = true;
        # Actions is deferred. Only opt-in experimental runner fixtures enable it.
        actions.ENABLED = config.scetrov.services.forgejo.runner.enable;
        log = {
          MODE = "console";
          LEVEL = "Info";
        };
      };
    };

    # Source-scoped SSH openings only; port 22 and the shared HTTPS listener
    # remain managed by their existing modules. Support both NixOS backends.
    networking.firewall =
      if config.networking.nftables.enable then
        {
          extraInputRules = ''
            ip saddr { ${lib.concatStringsSep ", " privateIPv4} } tcp dport 2222 accept
            ip6 saddr { ${lib.concatStringsSep ", " privateIPv6} } tcp dport 2222 accept
          '';
        }
      else
        {
          extraCommands = lib.concatMapStringsSep "\n" (
            rule: "${rule.tool} -A nixos-fw -p tcp -s ${rule.source} --dport 2222 -j nixos-fw-accept"
          ) sshRules;
          extraStopCommands = lib.concatMapStringsSep "\n" (
            rule:
            "${rule.tool} -D nixos-fw -p tcp -s ${rule.source} --dport 2222 -j nixos-fw-accept 2>/dev/null || true"
          ) sshRules;
        };

    services.caddy = {
      enable = true;
      virtualHosts."source.net.scetrov.live" = {
        useACMEHost = "scetrov.live";
        extraConfig = ''
          @notPrivate {
            not remote_ip ${lib.concatStringsSep " " (privateIPv4 ++ privateIPv6)}
          }
          respond @notPrivate "Forbidden" 403

          @internal path /metrics /metrics/* /api/internal /api/internal/*
          respond @internal "Not Found" 404

          encode zstd gzip
          # Native OIDC and Git/API tokens: deliberately no forward_auth.
          reverse_proxy 127.0.0.1:3002
        '';
      };
    };
  };
}
