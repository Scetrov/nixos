{ config, pkgs, ... }:

{
  security.sudo.wheelNeedsPassword = false;

  services.openssh = {
    enable = true;
    ports = [ 22 ];
    settings = {
      PasswordAuthentication = true;
      AllowUsers = [ "scetrov" ];
      UseDns = true;
      X11Forwarding = false;
      PermitRootLogin = "no";
    };
  };

  services.pcscd.enable = true;

  security.pam.yubico = {
    enable = true;
    debug = true;
    mode = "challenge-response";
    id = [ "11073070" ];
  };
}
