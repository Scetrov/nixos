{ config, ... }:

{
  networking = {
    wireless.enable = true;
    networkmanager.enable = false;
    hostName = "woodford";
    defaultGateway = "10.229.0.1";
    interfaces.wlo0.ipv4.addresses = [
      {
        address = "10.229.0.40";
        prefixLength = 16;
      }
    ];
  };
}
