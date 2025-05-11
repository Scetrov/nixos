{ config, ...}:

{
  services.immich = {
    enable = true;
    port = 3000;
    host = "immich.net.scetrov.live";
  };

  networking = {
    hosts = {
      "10.229.10.2" = [
        "immich.net.scetrov.live"
      ];
    };
  };
}