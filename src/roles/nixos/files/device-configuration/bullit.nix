{ config, ... }:

{
  networking = {
    wireless.enable = false;
    networkmanager.enable = true;
    hostName = "bullit";
    defaultGateway = "10.229.0.1";
    interfaces.eth0.ipv4.addresses = [
      {
        address = "10.229.0.39";
        prefixLength = 16;
      }
    ];
  };
}
