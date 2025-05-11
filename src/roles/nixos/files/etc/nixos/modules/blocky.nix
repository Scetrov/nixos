{ config, ... }:

{
  networking.firewall.allowedTCPPorts = [ 53 4000 ];
  networking.firewall.allowedUDPPorts = [ 53 ];

  networking = {
    nameservers = [
      "127.0.0.1" # blocky
      "::1"
    ];
    networkmanager.dns = "none";
  };

  services.blocky = {
    enable = true;
    settings = {
      ports.dns = "0.0.0.0:53";
      ports.http = "127.0.0.1:4000";
      upstreams.groups.default = [
        "https://one.one.one.one/dns-query" # Cloudflare
        "https://dns.google/dns-query" # Google
        "https://dns.quad9.net/dns-query" # Quad9
      ];
      bootstrapDns = {
        upstream = "https://one.one.one.one/dns-query";
        ips = [
          "1.1.1.1"
          "1.0.0.1"
        ];
      };
      blocking = {
        denyLists = {
          abuse = [ "https://blocklistproject.github.io/Lists/abuse.txt" ];
          drugs = [ "https://blocklistproject.github.io/Lists/drugs.txt" ];
          fraud = [ "https://blocklistproject.github.io/Lists/fraud.txt" ];
          gambling = [ "https://blocklistproject.github.io/Lists/gambling.txt" ];
          malware = [ "https://blocklistproject.github.io/Lists/malware.txt" ];
          phishing = [ "https://blocklistproject.github.io/Lists/phishing.txt" ];
          piracy = [ "https://blocklistproject.github.io/Lists/piracy.txt" ];
          porn = [ "https://blocklistproject.github.io/Lists/porn.txt" ];
          scam = [ "https://blocklistproject.github.io/Lists/scam.txt" ];
        };
        clientGroupsBlock = {
          default = [
            "adult"
            "malware"
            "phishing"
          ];
        };
      };
      caching = {
        minTime = "5m";
        maxTime = "30m";
        prefetching = true;
      };
      prometheus = {
        enable = true;
      };
      hostsFile = {
        sources = [ "/etc/hosts" ];
      };
    };
  };
}
