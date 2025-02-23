{ pkgs, lib, ... }:
let
  unstable = import <nixos-unstable>;
in {
  environment.systemPackages = [
    # For debugging and troubleshooting Secure Boot.
    pkgs.sbctl
    # Needed to use the TPM2 chip with `systemd-cryptenroll`
    pkgs.tpm2-tss
    pkgs.clevis
  ];

  # Lanzaboote currently replaces the systemd-boot module.
  # This setting is usually set to true in configuration.nix
  # generated at installation time. So we force it to false
  # for now.
  boot.loader.systemd-boot.enable = lib.mkForce false;

  boot.lanzaboote = {
    enable = true;
    pkiBundle = "/var/lib/sbctl";
  };
}
