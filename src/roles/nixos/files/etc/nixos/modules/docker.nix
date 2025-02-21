{ config, ... }:

{
  virtualisation.docker.enable = true;
  services.dockerRegistry.enableGarbageCollect = true;
}
