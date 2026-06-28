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
  homeAssistantPrometheusEntities = [
    "sensor.utility_room_sensor_temperature"
    "sensor.upstairs_hallway_sensor_temperature"
    "sensor.kitchen_sensor_temperature"
    "sensor.bathroom_sensor_temperature"
    "sensor.wifi_smart_switch_temperature"
    "sensor.wifi_smart_switch_humidity"
    "sensor.wifi_smart_switch_carbon_dioxide"
    "sensor.wifi_smart_switch_air_quality"
    "sensor.wifi_smart_switch_temperature_2"
    "sensor.wifi_smart_switch_humidity_2"
    "sensor.wifi_smart_switch_pm2_5"
    "sensor.wifi_smart_switch_pm10"
    "sensor.wifi_smart_switch_air_quality_2"
    "sensor.indoor_outdoor_meter_4bdd_temperature"
    "sensor.indoor_outdoor_meter_4bdd_humidity"
    "sensor.indoor_outdoor_meter_dbb6_temperature"
    "sensor.indoor_outdoor_meter_dbb6_humidity"
    "sensor.indoor_outdoor_meter_6d05_temperature"
    "sensor.indoor_outdoor_meter_6d05_humidity"
    "sensor.indoor_outdoor_meter_9aff_temperature"
    "sensor.indoor_outdoor_meter_9aff_humidity"
    "sensor.thermo_hygrometer_office_temperature"
    "sensor.thermo_hygrometer_office_humidity"
    "sensor.indoor_outdoor_meter_3393_temperature"
    "sensor.indoor_outdoor_meter_3393_humidity"
    "sensor.indoor_outdoor_meter_1d40_temperature"
    "sensor.indoor_outdoor_meter_1d40_humidity"
    "sensor.thermo_hygrometer_living_area_temperature"
    "sensor.thermo_hygrometer_living_area_humidity"
    "sensor.thermo_hygrometer_outside_shed_temperature"
    "sensor.thermo_hygrometer_outside_shed_humidity"
  ];
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
            user: "General User"
          features:
            default_redirect: true

        prometheus:
          namespace: "homeassistant"
          requires_auth: true
          filter:
            include_entities:
    ${lib.concatMapStringsSep "\n" (
      entityId: "          - ${entityId}"
    ) homeAssistantPrometheusEntities}

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

    bluetooth.enable = lib.mkEnableOption "Home Assistant Bluetooth access";
  };

  config = lib.mkIf cfg.enable {
    age.secrets.home_assistant_metrics_token = {
      file = /root/secrets/home_assistant_metrics_token.age;
      owner = "prometheus";
      group = "prometheus";
      mode = "0400";
    };

    hardware.bluetooth = lib.mkIf cfg.bluetooth.enable {
      enable = true;
      powerOnBoot = true;
    };

    virtualisation.oci-containers.containers = {
      homeassistant = {
        image = "ghcr.io/home-assistant/home-assistant:stable";
        autoStart = true;
        environment = {
          TZ = "Europe/London";
        };
        volumes = [
          "${homeAssistantStateDir}:/config"
        ]
        ++ lib.optionals cfg.bluetooth.enable [
          "/run/dbus:/run/dbus:ro"
        ];
        extraOptions = [
          "--network=host"
        ]
        ++ lib.optionals cfg.bluetooth.enable [
          "--cap-add=NET_ADMIN"
          "--cap-add=NET_RAW"
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

    services.prometheus.checkConfig = lib.mkDefault "syntax-only";

    services.prometheus.scrapeConfigs = lib.mkAfter [
      {
        job_name = "home-assistant";
        metrics_path = "/api/prometheus";
        scheme = "http";
        authorization = {
          type = "Bearer";
          credentials_file = config.age.secrets.home_assistant_metrics_token.path;
        };
        static_configs = [
          {
            targets = [ "127.0.0.1:8123" ];
            labels = {
              service = "home-assistant";
            };
          }
        ];
      }
    ];

    networking.firewall.allowedUDPPorts = [
      1900 # SSDP / UPnP discovery
      5353 # mDNS discovery
    ];
  };
}
