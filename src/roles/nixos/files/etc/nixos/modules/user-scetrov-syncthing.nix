{ config, pkgs, ... }:
let
  baseconfig = {
    allowUnfree = true;
  };
  unstable = import <nixos-unstable> { config = baseconfig; };
in
{
  services.syncthing = {
    enable = true;
    user = "scetrov";

    dataDir = "/home/scetrov/Documents";
    configDir = "/home/scetrov/.config/syncthing";
    guiAddress = "syncthing.scetrov.local:8384";

    overrideDevices = true;
    overrideFolders = true;

    openDefaultPorts = true;

    settings = {
      devices = {
        "woodford" = { id = "BCXATW4-QDVK6DP-G42DTSY-R62SFE3-EKSGV4I-EAIPXE2-HUK7SOX-6KJP5A7"; };
        "habiki" = { id = "6WMNQCS-LMHAQTF-Z5EY4BP-GA75H6W-6CZX5J6-6KXSHV6-RMYNKEV-LZHFMQU"; };
        "bullit" = { id = "4AFWIQD-ZRNKCFV-HJLVAWH-RLWZC5I-XHVDDKR-3RXPNDV-7MWYEVW-XFZCTQ5"; };
        "molasses" = { id = "QYQEVGE-EXSWWA3-SDME3KG-I5KMUBI-SE346WH-XUBAX4Q-KGZFRZF-HVKYCQ3"; };
        "razer" = { id = "VCQZ5XZ-WK6HKND-BL6S3AU-2HCUFSH-RG6MLJE-K2KHOZO-BBLWOZX-AUZPZAE"; };
      };
      folders = {
        "passwords" = {
          path = "/home/scetrov/Documents/passwords";
          devices = [ "woodford" "habiki" "bullit" ];
        };
        "shared" = {
          path = "/home/scetrov/Documents/shared";
          devices = [ "woodford" "habiki" "bullit" "molasses" "razer" ];
        };
      };
      options = {
        "urAccepted" = 99;
      };
      gui = {
        user = "scetrov";
        password = "$2a$10$yU8h0TKUwPgoM6Dx99TPk.wDagF6/imHgfj1IWyZpM7281ev2nZD6";
        tls = true;
      };
    };
  };

  security.pki.certificateFiles = [
    /home/scetrov/.config/syncthing/https-key.pem
  ];
}

