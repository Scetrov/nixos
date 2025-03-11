{ config, ... }:
let
  baseconfig = { allowUnfree = true; };
  unstable = import <nixos-unstable> { config = baseconfig; };
in {
  services.cloudflared = {
    enable = true;
    tunnels = {
      "woodford-tunnel" = {
        default = "http_status:404";
        ingress = {
          "api.killboard.nonprod.reapers.scetrov.live" = "http://localhost:5209";
        };
        credentialsFile = "/var/lib/cloudflared/woodford.json";
        co
      };
    };
  };
}