{ config, pkgs, ... }:

{
  boot.kernel.sysctl = {
    # allow unprivileged ports < 1024.
    # ref: https://ar.al/2022/08/30/dear-linux-privileged-ports-must-die/
    "net.ipv4.ip_unprivileged_port_start" = 0;
  };

  virtualisation = {
    containers.enable = true;

    podman = {
      enable = true;
      dockerSocket.enable = true;
      autoPrune = {
        enable = true;
        dates = "daily";
        flags = [ "--all" ];
      };
      dockerCompat = true;
      extraPackages = [
        pkgs.podman-compose
      ];
      defaultNetwork.settings = {
        dns_enabled = true;
        dns = [ "1.1.1.1" "8.8.8.8" ];
      };
    };
  
    oci-containers.backend = "podman";
  };

  # allow for DNS across the podman[0-9] interface
  networking.firewall.interfaces."podman+".allowedUDPPorts = [ 53 ];

  services.dockerRegistry.enableGarbageCollect = true;
}
