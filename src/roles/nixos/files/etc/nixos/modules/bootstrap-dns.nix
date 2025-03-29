{ config, ... }:

{
  networking = {
    nameservers = [
      "1.1.1.2"
      "1.0.0.2"
      "8.8.8.8"
      "8.8.8.4"
    ];
    networkmanager.dns = "none";
  };
}
