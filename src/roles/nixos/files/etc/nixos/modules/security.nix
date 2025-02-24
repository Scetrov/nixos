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

  security = {
    pam.u2f.enable = true;
  };

  security.pam.services = {
    login.u2fAuth = true;
    sudo.u2fAuth = true;
  };
  
  services = {
    pcscd.enable = true;

    udev = {
      packages = [
        pkgs.yubikey-personalization
      ];
    };
  };
}
