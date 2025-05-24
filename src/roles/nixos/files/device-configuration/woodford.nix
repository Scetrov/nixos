{ config, ... }:

{
  imports = [
    #./modules/cloudflared-woodford.nix
    ./modules/home-wifi.nix
    ./modules/local-networking.nix
    ./modules/prism-launcher.nix
    ./modules/user-scetrov-gui.nix
    ./modules/user-scetrov-syncthing.nix
    ./modules/xserver.nix
  ];

  services.xserver.videoDrivers = [ "nvidia" ];

  hardware.graphics = {
    enable = true;
  };

  networking.hostName = "woodford";

  hardware.nvidia = {
    package = config.boot.kernelPackages.nvidiaPackages.stable;
    modesetting.enable = true;
    powerManagement.enable = false;
    powerManagement.finegrained = false;
    open = false;
    nvidiaSettings = true;
    prime = {
      nvidiaBusId = "PCI:1:0:0";
      intelBusId = "PCI:0:2:0";
    };
  };
}
