{ config, ... }:

{
  age.secrets.wireless_pskraw.file = /root/secrets/wireless_pskraw.age;
  age.secrets.wireless_ssid.file = /root/secrets/wireless_ssid.age;

  networking = {
    hostName = "woodford";
    networkmanager = {
      enable = true;
      ensureProfiles = {
        environmentFiles = [
          config.age.secrets.wireless_pskraw.path
          config.age.secrets.wireless_ssid.path
        ];

        profiles = {
          "home-wifi" = {
            connection = {
              id = "home-wifi";
              type = "wifi";
              interface-name = "wlo1";
            };
            ipv4 = {
              method = "auto";
            };
            ipv6 = {
              method = "auto";
            };
            wifi = {
              mode = "infrastructure";
              ssid = "$WIRELESS_SSID";
            };
            wifi-security = {
              auth-alg = "open";
              key-mgmt = "wpa-psk";
              pskRaw = "$WIRELESS_PSKRAW";
            };
          };
        };
      };
    };
  };
}
