{ config, ...}:

{
  services.immich = {
    enable = true;
    port = 3000;
    host = "habiki.scetrov.live";
  };
}