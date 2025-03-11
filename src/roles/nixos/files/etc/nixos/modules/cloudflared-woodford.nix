{ config, ... }:
let
  baseconfig = { allowUnfree = true; };
  unstable = import <nixos-unstable> { config = baseconfig; };
in {
  services.cloudflared = {
    enable = true;
    tunnels = {
      "your-tunnel-name" = {
        default = "http_status:404";
        ingress = {
          "api.killboard.nonprod.reapers.scetrov.live" = “http://localhost:5209”;
        };
        credentialsFile = “/var/lib/cloudflared/woodford.json”;
      };
    };
  };
}