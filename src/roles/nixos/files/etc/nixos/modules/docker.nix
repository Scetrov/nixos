{ config, pkgs, ... }:

{
  virtualisation.podman = {
    enable = true;
    dockerSocket.enable = true;
    autoPrune.enable = true;
    dockerCompat = true;
    autoPrune.dates = "daily";
    extraPackages = [
      pkgs.podman-compose
    ];
  };
  
  services.dockerRegistry.enableGarbageCollect = true;
}
