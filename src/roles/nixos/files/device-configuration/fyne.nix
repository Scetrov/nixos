{ config, ... }:

{
  imports = [
    "${fetchTarball "https://github.com/NixOS/nixos-hardware/tarball/master"}/raspberry-pi/4"
  ];

  networking = {
    wireless.enable = false;
    networkmanager.enable = true;
    hostName = "bullit";
    defaultGateway = "10.229.0.1";
    interfaces.eth0.ipv4.addresses = [
      {
        address = "10.229.10.1";
        prefixLength = 16;
      }
    ];
  };
}
