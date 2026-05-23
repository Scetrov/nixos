{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.scetrov.services.home-assistant;
  oidcClientId = "home-assistant";
  oidcProviderSlug = "home-assistant-oidc";
  homeAssistantAssets = ../home-assistant;
  homeAssistantStateDir = "/var/lib/homeassistant";
  matterServerStateDir = "/var/lib/matter-server";
  matterServerImage = "ghcr.io/matter-js/python-matter-server:stable";
  matterServerPort = 5580;
  configurationYaml = pkgs.writeText "home-assistant-configuration.yaml" ''
    homeassistant:
      time_zone: "Europe/London"
      elevation: 50
      currency: "GBP"
      country: "GB"
      language: "en-GB"

    # Loads default set of integrations. Do not remove.
    default_config:

    http:
      use_x_forwarded_for: true
      trusted_proxies:
        - 127.0.0.1
        - ::1
        - 10.229.0.0/16

    auth_oidc:
      client_id: "${oidcClientId}"
      discovery_url: "https://identity.net.scetrov.live/application/o/${oidcProviderSlug}/.well-known/openid-configuration"
      display_name: "Authentik"
      roles:
        admin: "authentik Admins"
        user: "All Applications"
      features:
        default_redirect: true

    # Load frontend themes from the themes folder
    frontend:
      themes: !include_dir_merge_named themes

    automation: !include automations.yaml
    script: !include scripts.yaml
    scene: !include scenes.yaml
  '';
in
{
  options.scetrov.services.home-assistant = {
    enable = lib.mkEnableOption "Home Assistant service";

    matter.enable = lib.mkEnableOption "Home Assistant Matter Server";
  };

  config = lib.mkIf cfg.enable {
    virtualisation.oci-containers.containers = {
      homeassistant = {
        image = "ghcr.io/home-assistant/home-assistant:stable";
        autoStart = true;
        environment = {
          TZ = "Europe/London";
        };
        volumes = [
          "${homeAssistantStateDir}:/config"
        ];
        extraOptions = [
          "--network=host"
        ];
      };
    }
    // lib.optionalAttrs cfg.matter.enable {
      "matter-server" = {
        image = matterServerImage;
        autoStart = true;
        cmd = [
          "--storage-path"
          "/data"
          "--paa-root-cert-dir"
          "/data/credentials"
          "--listen-address"
          "127.0.0.1"
          "--port"
          (toString matterServerPort)
        ];
        volumes = [
          "${matterServerStateDir}:/data"
        ];
        extraOptions = [
          "--network=host"
          "--security-opt=apparmor=unconfined"
        ];
      };
    };

    systemd.tmpfiles.rules = [
      "d ${homeAssistantStateDir} 0750 root root -"
    ]
    ++ lib.optionals cfg.matter.enable [
      "d ${matterServerStateDir} 0750 root root -"
    ];

    system.activationScripts.homeAssistantConfiguration = ''
      install -d -m 0750 ${homeAssistantStateDir}
      install -d -m 0755 ${homeAssistantStateDir}/custom_components/auth_oidc
      rm -rf ${homeAssistantStateDir}/custom_components/auth_oidc/*
      ${pkgs.unzip}/bin/unzip -q ${../home-assistant/hass-oidc-auth-v1.1.0.zip} -d ${homeAssistantStateDir}/custom_components/auth_oidc
      install -m 0644 ${configurationYaml} ${homeAssistantStateDir}/configuration.yaml
      install -m 0644 ${homeAssistantAssets}/automations.yaml ${homeAssistantStateDir}/automations.yaml
      install -m 0644 ${homeAssistantAssets}/scripts.yaml ${homeAssistantStateDir}/scripts.yaml
      install -m 0644 ${homeAssistantAssets}/scenes.yaml ${homeAssistantStateDir}/scenes.yaml
      install -d -m 0755 ${homeAssistantStateDir}/.storage
      ${lib.optionalString cfg.matter.enable ''
        install -d -m 0750 ${matterServerStateDir}
      ''}
      cat > ${homeAssistantStateDir}/.storage/onboarding <<'EOF'
      {
        "version": 4,
        "minor_version": 1,
        "key": "onboarding",
        "data": {
          "done": [
            "user",
            "core_config",
            "analytics",
            "integration"
          ]
        }
      }
      EOF
      chmod 0600 ${homeAssistantStateDir}/.storage/onboarding
    '';

    systemd.services.home-assistant-bootstrap-owner = {
      description = "Bootstrap Home Assistant owner account";
      after = [ "podman-homeassistant.service" ];
      requires = [ "podman-homeassistant.service" ];
      wantedBy = [ "multi-user.target" ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
      };
      script = ''
        set -euo pipefail

        password_file=${homeAssistantStateDir}/.bootstrap-owner-password
        if [ ! -f "$password_file" ]; then
          ${pkgs.openssl}/bin/openssl rand -base64 36 > "$password_file"
          chmod 0600 "$password_file"
        fi

        for _ in $(seq 1 60); do
          if ${pkgs.podman}/bin/podman exec homeassistant python -m homeassistant --script auth -c /config list >/tmp/home-assistant-users 2>/tmp/home-assistant-auth.err; then
            break
          fi
          sleep 2
        done

        if grep -q "Total users: 0" /tmp/home-assistant-users; then
          ${pkgs.podman}/bin/podman exec homeassistant python -m homeassistant --script auth -c /config add scetrov-bootstrap "$(cat "$password_file")"
        fi
      '';
    };

    networking.firewall.allowedUDPPorts = [
      1900 # SSDP / UPnP discovery
      5353 # mDNS discovery
    ];
  };
}
