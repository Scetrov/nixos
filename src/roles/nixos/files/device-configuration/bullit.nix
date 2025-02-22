{ config, ... }:

{
  networking = {
    wireless.enable = false;
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
