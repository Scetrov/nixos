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

  services.pcscd.enable = false;

  security.pam.yubico = {
    enable = true;
    debug = true;
    mode = "challenge-response";
    id = [ "11073070" ];
  };

  services.udev.extraRules = ''
    ACTION!="add|change", GOTO="yubikey_end"

    # Udev rule for YubiKey 5 series (e.g. YubiKey 5 NFC)
    ATTRS{idVendor}=="1050", ATTRS{idProduct}=="0113|0114|0115|0116|0120|0402|0403|0406|0407|0410", \
        ENV{ID_SECURITY_TOKEN}="1"

    LABEL="yubikey_end"
  '';
  
}
