{ config, ...}:

{
  services.immich = {
    enable = true;
    port = 3000;
    host = "immich.net.scetrov.live";
  };
}