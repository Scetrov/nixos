{ config, pkgs, ... }:

{
  virtualisation = {
    containers.enable = true;

    podman = {
      enable = true;
      dockerSocket.enable = false;
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
  networking.firewall.interfaces."podman+".allowedTCPPorts = [ 3005 ];

  services.dockerRegistry.enableGarbageCollect = true;
}
