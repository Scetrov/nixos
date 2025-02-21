{ config, pkgs, ...}:
{
  services.printing.enable = false;

  hardware.pulseaudio.enable = false;
  security.rtkit.enable = true;
  services.pipewire.enable = true;
}