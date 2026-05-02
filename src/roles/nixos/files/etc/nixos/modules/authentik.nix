{ config, lib, pkgs, ... }:

let
  cfg = config.scetrov.services.authentik;
  stateDir = "/var/lib/authentik";
  dataDir = "${stateDir}/data";
  templatesDir = "${stateDir}/templates";
  authentikEnvFile = "${stateDir}/authentik.env";
  grafanaApplicationSlug = "grafana";
  grafanaRedirectUri = "https://metrics.net.scetrov.live/grafana/login/generic_oauth";
  grafanaLogoutUri = "https://metrics.net.scetrov.live/grafana/logout";
in
{
  options.scetrov.services.authentik = {
    enable = lib.mkEnableOption "Authentik identity service";

    domain = lib.mkOption {
      type = lib.types.str;
      default = "identity.net.scetrov.live";
      description = "Public domain used for the Authentik web UI.";
    };

    port = lib.mkOption {
      type = lib.types.port;
      default = 9000;
      description = "Local Authentik HTTP port proxied by Caddy.";
    };

    image = lib.mkOption {
      type = lib.types.str;
      default = "ghcr.io/goauthentik/server:2025.10";
      description = "Container image used for the Authentik server and worker.";
    };
  };

  config = lib.mkIf cfg.enable {
    age.secrets.authentik_secret_key = {
      file = /root/secrets/authentik_secret_key.age;
      owner = "root";
      group = "root";
      mode = "0400";
    };

    age.secrets.authentik_postgresql_password = {
      file = /root/secrets/authentik_postgresql_password.age;
      owner = "root";
      group = "root";
      mode = "0400";
    };

    age.secrets.authentik_admin_user = {
      file = /root/secrets/authentik_admin_user.age;
      owner = "root";
      group = "root";
      mode = "0400";
    };

    age.secrets.authentik_password = {
      file = /root/secrets/authentik_password.age;
      owner = "root";
      group = "root";
      mode = "0400";
    };

    age.secrets.authentik_bootstrap_token = {
      file = /root/secrets/authentik_bootstrap_token.age;
      owner = "root";
      group = "root";
      mode = "0400";
    };

    age.secrets.grafana_authentik_client_id = {
      file = /root/secrets/grafana_authentik_client_id.age;
      owner = "root";
      group = "root";
      mode = "0400";
    };

    age.secrets.grafana_authentik_client_secret = {
      file = /root/secrets/grafana_authentik_client_secret.age;
      owner = "root";
      group = "root";
      mode = "0400";
    };

    networking.firewall.allowedTCPPorts = [ 80 443 ];

    systemd.tmpfiles.rules = [
      "d ${stateDir} 0750 root root - -"
      "d ${dataDir} 0750 root root - -"
      "d ${templatesDir} 0750 root root - -"
    ];

    systemd.services.authentik-postgresql-init = {
      description = "Prepare PostgreSQL for Authentik";
      after = [ "postgresql.target" ];
      requires = [ "postgresql.target" ];
      before = [
        "authentik-bootstrap.service"
        "podman-authentik-server.service"
        "podman-authentik-worker.service"
      ];
      wantedBy = [ "multi-user.target" ];
      path = [ config.services.postgresql.package pkgs.gnugrep ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        User = "postgres";
        Group = "postgres";
        LoadCredential = [ "db_password:${config.age.secrets.authentik_postgresql_password.path}" ];
      };
      script = ''
        set -euo pipefail

        db_password="$(<"$CREDENTIALS_DIRECTORY/db_password")"
        db_password="''${db_password//\'/\'\'}"

        psql -tAc "SELECT 1 FROM pg_roles WHERE rolname = 'authentik'" | grep -q 1 || \
          psql -tAc 'CREATE ROLE "authentik" LOGIN'
        psql -tAc "ALTER ROLE \"authentik\" WITH LOGIN PASSWORD '$db_password'"
      '';
    };

    systemd.services.authentik-bootstrap = {
      description = "Prepare Authentik container environment";
      wantedBy = [ "multi-user.target" ];
      after = [ "authentik-postgresql-init.service" ];
      requires = [ "authentik-postgresql-init.service" ];
      before = [
        "podman-authentik-server.service"
        "podman-authentik-worker.service"
      ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
      };
      script = ''
        set -euo pipefail

        ${pkgs.coreutils}/bin/install -d -m 0750 ${stateDir} ${dataDir} ${templatesDir}

        secret_key="$(${pkgs.coreutils}/bin/tr -d '\n' < ${config.age.secrets.authentik_secret_key.path})"
        db_password="$(${pkgs.coreutils}/bin/tr -d '\n' < ${config.age.secrets.authentik_postgresql_password.path})"
        bootstrap_password="$(${pkgs.coreutils}/bin/tr -d '\n' < ${config.age.secrets.authentik_password.path})"
        bootstrap_token="$(${pkgs.coreutils}/bin/tr -d '\n' < ${config.age.secrets.authentik_bootstrap_token.path})"

        umask 077
        : > ${authentikEnvFile}
        ${pkgs.coreutils}/bin/chmod 0600 ${authentikEnvFile}

        ${pkgs.coreutils}/bin/printf '%s\n' 'AUTHENTIK_POSTGRESQL__HOST=host.containers.internal' >> ${authentikEnvFile}
        ${pkgs.coreutils}/bin/printf '%s\n' 'AUTHENTIK_POSTGRESQL__NAME=authentik' >> ${authentikEnvFile}
        ${pkgs.coreutils}/bin/printf '%s\n' 'AUTHENTIK_POSTGRESQL__USER=authentik' >> ${authentikEnvFile}
        ${pkgs.coreutils}/bin/printf '%s\n' 'AUTHENTIK_POSTGRESQL__PORT=5432' >> ${authentikEnvFile}
        ${pkgs.coreutils}/bin/printf 'AUTHENTIK_POSTGRESQL__PASSWORD=%s\n' "$db_password" >> ${authentikEnvFile}
        ${pkgs.coreutils}/bin/printf 'AUTHENTIK_BOOTSTRAP_PASSWORD=%s\n' "$bootstrap_password" >> ${authentikEnvFile}
        ${pkgs.coreutils}/bin/printf 'AUTHENTIK_BOOTSTRAP_TOKEN=%s\n' "$bootstrap_token" >> ${authentikEnvFile}
        ${pkgs.coreutils}/bin/printf 'AUTHENTIK_SECRET_KEY=%s\n' "$secret_key" >> ${authentikEnvFile}
      '';
    };

    systemd.services.authentik-provision = {
      description = "Provision Authentik users and Grafana OIDC integration";
      wantedBy = [ "multi-user.target" ];
      after = [
        "authentik-bootstrap.service"
        "podman-authentik-server.service"
        "podman-authentik-worker.service"
      ];
      requires = [
        "authentik-bootstrap.service"
        "podman-authentik-server.service"
        "podman-authentik-worker.service"
      ];
      path = [ pkgs.coreutils pkgs.curl pkgs.jq ];
      serviceConfig = {
        Type = "oneshot";
        Restart = "on-failure";
        RestartSec = "5s";
      };
      script = ''
        set -euo pipefail

        api_base="http://127.0.0.1:${toString cfg.port}/api/v3"
        admin_username="$(${pkgs.coreutils}/bin/tr -d '\n' < ${config.age.secrets.authentik_admin_user.path})"
        admin_password="$(${pkgs.coreutils}/bin/tr -d '\n' < ${config.age.secrets.authentik_password.path})"
        bootstrap_token="$(${pkgs.coreutils}/bin/tr -d '\n' < ${config.age.secrets.authentik_bootstrap_token.path})"
        grafana_client_id="$(${pkgs.coreutils}/bin/tr -d '\n' < ${config.age.secrets.grafana_authentik_client_id.path})"
        grafana_client_secret="$(${pkgs.coreutils}/bin/tr -d '\n' < ${config.age.secrets.grafana_authentik_client_secret.path})"

        auth_header="Authorization: Bearer $bootstrap_token"

        api() {
          local method="$1"
          local path="$2"
          local data="''${3-}"
          local response_file http_code

          response_file="$(${pkgs.coreutils}/bin/mktemp)"
          if [ -n "$data" ]; then
            http_code="$(${pkgs.curl}/bin/curl \
              --silent --show-error \
              --output "$response_file" \
              --write-out '%{http_code}' \
              --request "$method" \
              --header "$auth_header" \
              --header 'Content-Type: application/json' \
              --data "$data" \
              "$api_base$path")"
          else
            http_code="$(${pkgs.curl}/bin/curl \
              --silent --show-error \
              --output "$response_file" \
              --write-out '%{http_code}' \
              --request "$method" \
              --header "$auth_header" \
              "$api_base$path")"
          fi

          if [ "$http_code" -lt 200 ] || [ "$http_code" -ge 300 ]; then
            echo "API request failed: $method $path (HTTP $http_code)" >&2
            ${pkgs.coreutils}/bin/cat "$response_file" >&2
            ${pkgs.coreutils}/bin/rm -f "$response_file"
            return 1
          fi

          ${pkgs.coreutils}/bin/cat "$response_file"
          ${pkgs.coreutils}/bin/rm -f "$response_file"
        }

        api_post_void() {
          local method="$1"
          local path="$2"
          local data="$3"
          local response_file http_code

          response_file="$(${pkgs.coreutils}/bin/mktemp)"
          http_code="$(${pkgs.curl}/bin/curl \
            --silent --show-error \
            --output "$response_file" \
            --write-out '%{http_code}' \
            --request "$method" \
            --header "$auth_header" \
            --header 'Content-Type: application/json' \
            --data "$data" \
            "$api_base$path")"

          if [ "$http_code" -lt 200 ] || [ "$http_code" -ge 300 ]; then
            echo "API request failed: $method $path (HTTP $http_code)" >&2
            ${pkgs.coreutils}/bin/cat "$response_file" >&2
            ${pkgs.coreutils}/bin/rm -f "$response_file"
            return 1
          fi

          ${pkgs.coreutils}/bin/rm -f "$response_file"
        }

        list_first() {
          local path="$1"
          local jq_filter="$2"

          api GET "$path" | ${pkgs.jq}/bin/jq -r "$jq_filter"
        }

        urlencode() {
          ${pkgs.jq}/bin/jq -nr --arg value "$1" '$value | @uri'
        }

        ensure_user() {
          local user_pk
          user_pk="$(list_first "/core/users/?username=$(urlencode "$admin_username")&page_size=100" '.results[0].pk // empty')"
          if [ -z "$user_pk" ]; then
            user_pk="$(api POST "/core/users/" "$(${pkgs.jq}/bin/jq -cn --arg username "$admin_username" '{username: $username, name: $username, is_active: true, groups: [], roles: []}')" | ${pkgs.jq}/bin/jq -r '.pk')"
          else
            api PATCH "/core/users/$user_pk/" "$(${pkgs.jq}/bin/jq -cn --arg username "$admin_username" '{name: $username, is_active: true}')" >/dev/null
          fi

          api_post_void POST "/core/users/$user_pk/set_password/" "$(${pkgs.jq}/bin/jq -cn --arg password "$admin_password" '{password: $password}')"
          echo "$user_pk"
        }

        ensure_group() {
          local group_uuid
          group_uuid="$(list_first "/core/groups/?name=authentik%20Admins&page_size=100" '.results[0].pk // empty')"
          if [ -z "$group_uuid" ]; then
            group_uuid="$(api POST "/core/groups/" '{"name":"authentik Admins","is_superuser":true}' | ${pkgs.jq}/bin/jq -r '.pk')"
          else
            api PATCH "/core/groups/$group_uuid/" '{"is_superuser":true}' >/dev/null
          fi
          echo "$group_uuid"
        }

        ensure_group_membership() {
          local group_uuid="$1"
          local user_pk="$2"
          local member_present

          member_present="$(api GET "/core/groups/$group_uuid/?include_users=true" | ${pkgs.jq}/bin/jq -r --argjson user_pk "$user_pk" 'any((.users_obj // [])[]?; .pk == $user_pk)')"
          if [ "$member_present" != "true" ]; then
            api_post_void POST "/core/groups/$group_uuid/add_user/" "$(${pkgs.jq}/bin/jq -cn --argjson pk "$user_pk" '{pk: $pk}')"
          fi
        }

        maybe_disable_bootstrap_user() {
          local admin_user_pk="$1"
          local bootstrap_user_pk

          if [ "$admin_username" = "akadmin" ]; then
            return 0
          fi

          bootstrap_user_pk="$(list_first "/core/users/?username=akadmin&page_size=100" '.results[0].pk // empty')"
          if [ -n "$bootstrap_user_pk" ] && [ "$bootstrap_user_pk" != "$admin_user_pk" ]; then
            api PATCH "/core/users/$bootstrap_user_pk/" '{"is_active":false}' >/dev/null
          fi
        }

        flow_pk() {
          local slug="$1"
          api GET "/flows/instances/$slug/" | ${pkgs.jq}/bin/jq -r '.pk'
        }

        scope_mapping_pk() {
          local scope_name="$1"
          local managed="$2"
          api GET "/propertymappings/provider/scope/?scope_name=$scope_name&page_size=100" \
            | ${pkgs.jq}/bin/jq -r --arg managed "$managed" '(.results[] | select(.managed == $managed) | .pk) // empty' \
            | ${pkgs.coreutils}/bin/head -n 1
        }

        ensure_provider() {
          local authorization_flow_pk="$1"
          local invalidation_flow_pk="$2"
          local openid_scope_pk="$3"
          local profile_scope_pk="$4"
          local email_scope_pk="$5"
          local entitlements_scope_pk="$6"
          local provider_id payload

          payload="$(${pkgs.jq}/bin/jq -cn \
            --arg name "Grafana" \
            --arg authorization_flow "$authorization_flow_pk" \
            --arg invalidation_flow "$invalidation_flow_pk" \
            --arg client_id "$grafana_client_id" \
            --arg client_secret "$grafana_client_secret" \
            --arg redirect_uri "${grafanaRedirectUri}" \
            --arg logout_uri "${grafanaLogoutUri}" \
            --arg openid_scope "$openid_scope_pk" \
            --arg profile_scope "$profile_scope_pk" \
            --arg email_scope "$email_scope_pk" \
            --arg entitlements_scope "$entitlements_scope_pk" \
            '{
              name: $name,
              authorization_flow: $authorization_flow,
              invalidation_flow: $invalidation_flow,
              client_type: "confidential",
              grant_types: ["authorization_code"],
              client_id: $client_id,
              client_secret: $client_secret,
              property_mappings: [$openid_scope, $profile_scope, $email_scope, $entitlements_scope],
              redirect_uris: [{matching_mode: "strict", url: $redirect_uri}],
              logout_uri: $logout_uri,
              logout_method: "frontchannel"
            }')"

          provider_id="$(list_first "/providers/oauth2/?client_id=$(urlencode "$grafana_client_id")&page_size=100" '.results[0].pk // empty')"
          if [ -z "$provider_id" ]; then
            provider_id="$(api POST "/providers/oauth2/" "$payload" | ${pkgs.jq}/bin/jq -r '.pk')"
          else
            api PATCH "/providers/oauth2/$provider_id/" "$payload" >/dev/null
          fi

          echo "$provider_id"
        }

        ensure_application() {
          local provider_id="$1"
          local application_pk
          local payload

          payload="$(${pkgs.jq}/bin/jq -cn \
            --arg name "Grafana" \
            --arg slug "${grafanaApplicationSlug}" \
            --arg meta_launch_url "https://metrics.net.scetrov.live/grafana" \
            --arg provider "$provider_id" \
            '{
              name: $name,
              slug: $slug,
              provider: $provider,
              meta_launch_url: $meta_launch_url,
              open_in_new_tab: false,
              meta_hide: false
            }')"

          application_pk="$(list_first "/core/applications/?slug=${grafanaApplicationSlug}&page_size=100" '.results[0].pk // empty')"
          if [ -z "$application_pk" ]; then
            application_pk="$(api POST "/core/applications/" "$payload" | ${pkgs.jq}/bin/jq -r '.pk')"
          else
            api PATCH "/core/applications/${grafanaApplicationSlug}/" "$payload" >/dev/null
          fi

          echo "$application_pk"
        }

        ensure_entitlement() {
          local application_pk="$1"
          local entitlement_name="$2"
          local entitlement_pk
          local payload

          payload="$(${pkgs.jq}/bin/jq -cn --arg name "$entitlement_name" --arg app "$application_pk" '{name: $name, app: $app}')"
          entitlement_pk="$(list_first "/core/application_entitlements/?app=$(urlencode "$application_pk")&name=$(urlencode "$entitlement_name")&page_size=100" '.results[0].pbm_uuid // empty')"
          if [ -z "$entitlement_pk" ]; then
            entitlement_pk="$(api POST "/core/application_entitlements/" "$payload" | ${pkgs.jq}/bin/jq -r '.pbm_uuid')"
          fi

          echo "$entitlement_pk"
        }

        ensure_user_entitlement_binding() {
          local entitlement_pk="$1"
          local user_pk="$2"
          local binding_exists

          binding_exists="$(api GET "/policies/bindings/?page_size=500" | ${pkgs.jq}/bin/jq -r --arg target "$entitlement_pk" --argjson user "$user_pk" 'any((.results // [])[]?; .target == $target and .user == $user)')"
          if [ "$binding_exists" != "true" ]; then
            api POST "/policies/bindings/" "$(${pkgs.jq}/bin/jq -cn --arg target "$entitlement_pk" --argjson user "$user_pk" '{target: $target, user: $user, order: 0}')" >/dev/null
          fi
        }

        for _ in $(${pkgs.coreutils}/bin/seq 1 120); do
          if ${pkgs.curl}/bin/curl --silent --show-error --fail --output /dev/null --header "$auth_header" "$api_base/core/users/me/"; then
            break
          fi
          ${pkgs.coreutils}/bin/sleep 2
        done

        admin_user_pk="$(ensure_user)"
        admin_group_uuid="$(ensure_group)"
        ensure_group_membership "$admin_group_uuid" "$admin_user_pk"
        maybe_disable_bootstrap_user "$admin_user_pk"

        authorization_flow_pk="$(flow_pk default-provider-authorization-implicit-consent)"
        invalidation_flow_pk="$(flow_pk default-provider-invalidation)"

        openid_scope_pk="$(scope_mapping_pk openid goauthentik.io/providers/oauth2/scope-openid)"
        profile_scope_pk="$(scope_mapping_pk profile goauthentik.io/providers/oauth2/scope-profile)"
        email_scope_pk="$(scope_mapping_pk email goauthentik.io/providers/oauth2/scope-email)"
        entitlements_scope_pk="$(scope_mapping_pk entitlements goauthentik.io/providers/oauth2/scope-entitlements)"

        provider_id="$(ensure_provider "$authorization_flow_pk" "$invalidation_flow_pk" "$openid_scope_pk" "$profile_scope_pk" "$email_scope_pk" "$entitlements_scope_pk")"
        application_pk="$(ensure_application "$provider_id")"

        grafana_admin_entitlement="$(ensure_entitlement "$application_pk" "Grafana Admins")"
        ensure_entitlement "$application_pk" "Grafana Editors" >/dev/null
        ensure_entitlement "$application_pk" "Grafana Viewers" >/dev/null
        ensure_user_entitlement_binding "$grafana_admin_entitlement" "$admin_user_pk"
      '';
    };

    systemd.services.podman-authentik-server = {
      after = [ "authentik-bootstrap.service" ];
      requires = [ "authentik-bootstrap.service" ];
    };

    systemd.services.podman-authentik-worker = {
      after = [ "authentik-bootstrap.service" ];
      requires = [ "authentik-bootstrap.service" ];
    };

    virtualisation.oci-containers.containers = {
      authentik-server = {
        image = cfg.image;
        autoStart = true;
        cmd = [ "server" ];
        environmentFiles = [ authentikEnvFile ];
        extraOptions = [ "--network=podman" "--shm-size=512m" ];
        ports = [ "127.0.0.1:${toString cfg.port}:9000" ];
        volumes = [
          "${dataDir}:/data:U"
          "${templatesDir}:/templates:U"
        ];
      };

      authentik-worker = {
        image = cfg.image;
        autoStart = true;
        cmd = [ "worker" ];
        environmentFiles = [ authentikEnvFile ];
        extraOptions = [ "--network=podman" "--shm-size=512m" ];
        volumes = [
          "${dataDir}:/data:U"
          "${templatesDir}:/templates:U"
        ];
      };
    };

    services.postgresql = {
      enable = true;
      enableTCPIP = true;
      authentication = lib.mkBefore ''
        host authentik authentik 10.88.0.0/16 scram-sha-256
      '';
      ensureDatabases = [ "authentik" ];
      ensureUsers = [
        {
          name = "authentik";
          ensureDBOwnership = true;
          ensureClauses = {
            login = true;
          };
        }
      ];
      settings.listen_addresses = lib.mkDefault "127.0.0.1,10.88.0.1";
    };

    services.caddy = {
      enable = true;
      virtualHosts."${cfg.domain}" = {
        useACMEHost = "scetrov.live";
        extraConfig = ''
          encode zstd gzip
          reverse_proxy 127.0.0.1:${toString cfg.port}
        '';
      };
    };
  };
}