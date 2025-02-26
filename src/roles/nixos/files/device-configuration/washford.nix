{ config, ... }:

{
  networking = {
    wireless.enable = false;
    networkmanager.enable = true;
    hostName = "washford";
    defaultGateway = "10.229.0.1";
    interfaces.eth0.ipv4.addresses = [
      {
        address = "10.229.5.162";
        prefixLength = 16;
      }
    ];
  };
}
