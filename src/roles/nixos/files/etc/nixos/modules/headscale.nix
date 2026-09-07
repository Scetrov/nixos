{
  config,
  lib,
  pkgs,
  ...
}:

let
  hostname = "headscale.net.scetrov.live";
  policyFile = "/etc/headscale/policy.hujson";
in
{
  # Token scope: Zone / DNS / Edit for the scetrov.live zone only. The DDNS
  # client needs an environment file rather than a bare token file.
  age.secrets.cloudflare_headscale_ddns_api_token = {
    file = /root/secrets/cloudflare_headscale_ddns_api_token.age;
    owner = "cloudflare-ddns";
    group = "cloudflare-ddns";
    mode = "0400";
  };

  services.cloudflare-ddns = {
    enable = true;
    credentialsFile = config.age.secrets.cloudflare_headscale_ddns_api_token.path;
    ip4Domains = [ hostname ];
    provider.ipv6 = "none";
    updateCron = "@every 5m";
    ttl = 1;
    # Traffic must reach Habiki's router-forwarded TCP listener directly.
    proxied = "false";
    recordComment = "Managed by Habiki Headscale DDNS";
  };

  # Habiki joins its own tailnet so private services can bind to a stable
  # Headscale address. Its one-time enrolment is handled idempotently by the
  # NixOS deployment role after tailscaled is available.
  services.tailscale.enable = true;

  services.headscale = {
    enable = true;
    address = "127.0.0.1";
    port = 8090;
    settings = {
      server_url = "https://${hostname}:8443";
      database = {
        type = "sqlite";
        sqlite = {
          path = "/var/lib/headscale/db.sqlite";
          write_ahead_log = true;
        };
      };
      dns = {
        magic_dns = true;
        base_domain = "tailnet.net.scetrov.live";
        override_local_dns = false;
        extra_records = [
          {
            name = "s3.tailnet.net.scetrov.live";
            type = "A";
            value = "100.64.0.1";
          }
        ];
      };
      # The debug and metrics listener must not be exposed through Caddy.
      metrics_listen_addr = "127.0.0.1:9091";
      policy = {
        mode = "file";
        path = policyFile;
      };
    };
  };

  # Headscale's NixOS module creates /var/lib/headscale as a service-owned
  # StateDirectory with restrictive permissions. Keep the policy declarative
  # while preserving the database and controller keys across rebuilds.
  environment.etc."headscale/policy.hujson".text = ''
    {
      "groups": {
        "group:admins": [],
        "group:project": []
      },
      "tagOwners": {
        "tag:admin": ["group:admins"],
        "tag:project": ["group:project"]
      },
      "acls": []
    }
  '';

  environment.systemPackages = [
    (pkgs.writeShellScriptBin "headscale-enrolment" ''
      set -euo pipefail

      usage() {
        echo "usage: headscale-enrolment create-user <name> | create-key <numeric-user-id> [1h|24h|7d] | revoke <key-id>" >&2
        exit 64
      }

      [ "$#" -ge 1 ] || usage
      case "$1" in
        create-user)
          [ "$#" -eq 2 ] || usage
          exec ${lib.getExe config.services.headscale.package} users create "$2"
          ;;
        create-key)
          [ "$#" -eq 2 ] || [ "$#" -eq 3 ] || usage
          expiration="''${3:-24h}"
          case "$expiration" in 1h|24h|7d) ;; *) usage ;; esac
          exec ${lib.getExe config.services.headscale.package} preauthkeys create --user "$2" --reusable --expiration "$expiration"
          ;;
        revoke)
          [ "$#" -eq 2 ] || usage
          exec ${lib.getExe config.services.headscale.package} preauthkeys expire --id "$2"
          ;;
        *) usage ;;
      esac
    '')
  ];

  assertions = [
    {
      assertion = config.services.headscale.address == "127.0.0.1";
      message = "Headscale must remain bound to loopback; Caddy is its only public listener.";
    }
    {
      assertion = config.services.headscale.settings.server_url == "https://${hostname}:8443";
      message = "Headscale must advertise its dedicated HTTPS endpoint on TCP 8443.";
    }
  ];
}
