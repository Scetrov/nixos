{ config, pkgs, ... }:

{
  boot.blacklistedKernelModules = [ "algif_aead" ];

  security.sudo.wheelNeedsPassword = true;
  security.sudo.extraRules = [
    {
      users = [ "scetrov" ];
      commands = [
        {
          command = "ALL";
          options = [ "NOPASSWD" ];
        }
      ];
    }
  ];

  services.openssh = {
    enable = true;
    ports = [ 22 ];
    openFirewall = true;
    settings = {
      PasswordAuthentication = false;
      KbdInteractiveAuthentication = false;
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
