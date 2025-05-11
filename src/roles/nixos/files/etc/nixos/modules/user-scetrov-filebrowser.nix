{ config, pkgs, ... }:
let
  baseconfig = {
    allowUnfree = true;
  };
  unstable = import <nixos-unstable> { config = baseconfig; };
in
{
  users.users.scetrov = {
    packages = with pkgs; [
      unstable.filebrowser
    ];
  };

  # write the config file to ~/.config/filebrowser/config.yaml
  # and set the permissions to 0600

  # execute filebrowser config init in ~/.config/filebrowser to create the database
  # and set the permissions to 0600

  # configure filebrowser to run in Podman as scetrov and bind mount the config, database and ~/Sync
  # add traefik labels to the Podman container
}
