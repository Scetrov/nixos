{ config, lib, ... }:

{
  options.blocky.bindAddr = lib.mkOption {
    type = lib.types.str;
    default = "0.0.0.0:53";
    description = "Bind address for the DNS server.";
  };

  config.networking = {
    firewall.allowedTCPPorts = [
      53
      4000
    ];
    firewall.allowedUDPPorts = [ 53 ];
    nameservers = [
      "10.229.53.1" # blocky on Fyne
      "10.229.53.2" # blocky on Habiki
    ];
    networkmanager.dns = "none";
  };

  config.services.blocky = {
    enable = true;
    settings = {
      ports.dns = config.blocky.bindAddr;
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
        blockType = "10.229.53.1";
        denylists = {
          abuse = [ "https://blocklistproject.github.io/Lists/abuse.txt" ];
          drugs = [ "https://blocklistproject.github.io/Lists/drugs.txt" ];
          fraud = [ "https://blocklistproject.github.io/Lists/fraud.txt" ];
          gambling = [ "https://blocklistproject.github.io/Lists/gambling.txt" ];
          malware = [ "https://blocklistproject.github.io/Lists/malware.txt" ];
          phishing = [ "https://blocklistproject.github.io/Lists/phishing.txt" ];
          piracy = [ "https://blocklistproject.github.io/Lists/piracy.txt" ];
          porn = [ "https://blocklistproject.github.io/Lists/porn.txt" ];
          scam = [ "https://blocklistproject.github.io/Lists/scam.txt" ];
          "miasma-mini-shai-hulud" = [
            ''
              # Miasma / Mini Shai-Hulud C2 domains and response IPs.
              # Use a wildcard for getsession.org to match the apex and subdomains.
              *.getsession.org
              t.m-kosche.com
              m-kosche.com
              api.masscan.cloud
              git-tanstack.com
              litter.catbox.moe
              audit.checkmarx.cx
              checkmarx.cx
              216.126.225.129
              185.95.159.32
              94.154.172.43
              91.195.240.123
            ''
          ];
        };
        allowlists = {
          "miasma-mini-shai-hulud" = [
            ''
              # Explicitly preserve legitimate developer infrastructure.
              # In Blocky, allowlists in the same group take precedence over denylists.
              github.com
              api.github.com
              anthropic.com
              api.anthropic.com
              registry.npmjs.org
            ''
          ];
        };
        clientGroupsBlock = {
          default = [
            "abuse"
            "drugs"
            "fraud"
            "gambling"
            "malware"
            "phishing"
            "piracy"
            "porn"
            "scam"
            "miasma-mini-shai-hulud"
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
