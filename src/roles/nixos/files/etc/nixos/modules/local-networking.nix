{ config, ... }:

{
  networking = {
    firewall.enable = true;

    hosts = {
      "127.0.0.1" = [
        "localhost"
        "syncthing.scetrov.local"
      ];
      "10.229.10.1" = [
        "fyne"
        "fyne.net.scetrov.live"
      ];
      "10.229.10.2" = [
        "habiki"
        "habiki.net.scetrov.live"
        "traefik.net.scetrov.live"
        "grafana.net.scetrov.live"
        "prometheus.net.scetrov.live"
        "json-rpc.sepolia.scetrov.live"
        "json-rpc.pyrope.scetrov.live"
      ];
      "10.229.10.10" = [
        "bullit"
        "bullit.net.scetrov.live"
      ];
      "10.229.10.11" = [
        "woodford"
        "woodford.net.scetrov.live"
      ];
    };
  };
}
