{ config, ... }:
let
  baseconfig = { allowUnfree = true; };
  unstable = import <nixos-unstable> { config = baseconfig; };
in {
  users.users.cloudflared = {
    isSystemUser = true;
    group = "cloudflared";
    description = "Cloudflared user for running tunnels";
  };
  # services.cloudflared = {
  #   enable = true;
  #   tunnels = {
  #     "woodford-tunnel" = {
  #       default = "http_status:404";
  #       ingress = {
  #         "api-killboard-nonprod-reapers.scetrov.live" = "http://localhost:5209";
  #       };
  #       credentialsFile = "/var/lib/cloudflared/woodford.json";
  #     };
  #   };
  # };
}