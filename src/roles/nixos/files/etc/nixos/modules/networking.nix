{ config, ... }:

{
  networking = {
    nameservers = [
      "127.0.0.1" # dnscrypt2-proxy
      "::1"
      "1.1.1.1" # Cloudflare
      "8.8.8.8" # Google
    ];
    networkmanager.dns = "none";
    firewall.enable = true;
    hosts = {
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

  services.dnscrypt-proxy2 = {
    enable = true;
    settings = {
      ipv6_servers = true;
      require_dnssec = true;
      sources.public-resolvers = {
        urls = [
          "https://raw.githubusercontent.com/DNSCrypt/dnscrypt-resolvers/master/v3/public-resolvers.md"
          "https://download.dnscrypt.info/resolvers-list/v3/public-resolvers.md"
        ];
        cache_file = "/var/cache/dnscrypt-proxy/public-resolvers.md";
        minisign_key = "RWQf6LRCGA9i53mlYecO4IzT51TGPpvWucNSCh1CBM0QTaLn73Y7GFO3";
      };
    };
  };
}
