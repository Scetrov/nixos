{ config, ... }:

{
  age.secrets.wireless_psk.file = /root/secrets/wireless_psk.age;

  networking = {
    hostName = "woodford";
    networkmanager = {
      enable = true;
      ensureProfiles = {
        environmentFiles = [
          config.age.secrets.wireless_psk.path
        ];

        profiles = {
          "Home WiFi" = {
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
              ssid = "simian.collingwood";
            };
            wifi-security = {
              auth-alg = "open";
              key-mgmt = "wpa-psk";
              psk = "$WIRELESS_PSK";
            };
          };
        };
      };
    };
  };
}
