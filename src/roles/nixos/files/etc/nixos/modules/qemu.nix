{ config, ... }:
let
  baseconfig = { allowUnfree = true; };
  unstable = import <nixos-unstable> { config = baseconfig; };
in {
  environment.systemPackages = with unstable; [
    qemu
    virt-manager
    virt-viewer
    spice
    spice-gtk
    win-virtio
    win-spice
    adwaita-icon-theme
  ];
}

