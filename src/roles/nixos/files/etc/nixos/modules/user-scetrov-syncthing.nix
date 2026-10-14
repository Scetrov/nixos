{ config, pkgs, ... }:
let
  baseconfig = {
    allowUnfree = true;
  };
  unstable = import <nixos-unstable> { config = baseconfig; };
in
{
  # Plaintext GUI password, age-encrypted at rest; the syncthing module
  # bcrypt-hashes it at activation and applies it via the REST API.
  age.secrets.syncthing_gui_password.file = /root/secrets/syncthing_gui_password.age;

  services.syncthing = {
    enable = true;
    user = "scetrov";

    dataDir = "/home/scetrov/Documents";
    configDir = "/home/scetrov/.config/syncthing";
    guiAddress = "syncthing.scetrov.local:8384";
    guiPasswordFile = config.age.secrets.syncthing_gui_password.path;

    overrideDevices = true;
    overrideFolders = true;

    openDefaultPorts = true;

    settings = {
      devices = {
        "habiki" = {
          id = "6WMNQCS-LMHAQTF-Z5EY4BP-GA75H6W-6CZX5J6-6KXSHV6-RMYNKEV-LZHFMQU";
        };
        "bullit" = {
          id = "4AFWIQD-ZRNKCFV-HJLVAWH-RLWZC5I-XHVDDKR-3RXPNDV-7MWYEVW-XFZCTQ5";
        };
        "molasses" = {
          id = "QYQEVGE-EXSWWA3-SDME3KG-I5KMUBI-SE346WH-XUBAX4Q-KGZFRZF-HVKYCQ3";
        };
        "razer" = {
          id = "VCQZ5XZ-WK6HKND-BL6S3AU-2HCUFSH-RG6MLJE-K2KHOZO-BBLWOZX-AUZPZAE";
        };
        "fyne" = {
          id = "7Z3NTU5-25WE7D3-AUFPYE4-BYT4GWZ-BCB7ZL7-BBQF5IB-JQ2FZCD-XJMTEQX";
        };
      };
      folders = {
        "passwords" = {
          path = "/home/scetrov/Documents/passwords";
          devices = [
            "habiki"
            "bullit"
            "fyne"
          ];
        };
        "shared" = {
          path = "/home/scetrov/Documents/shared";
          devices = [
            "habiki"
            "bullit"
            "molasses"
            "razer"
            "fyne"
          ];
        };
      };
      options = {
        "urAccepted" = 99;
      };
      gui = {
        user = "scetrov";
        tls = true;
      };
    };
  };

  security.pki.certificateFiles = [
    /home/scetrov/.config/syncthing/https-key.pem
  ];
}
