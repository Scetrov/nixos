{ config, pkgs, ... }:

{
  users.users.scetrov = {
    packages = with pkgs; [
      (prismlauncher.override {
        jdks = [
          zulu21
        ];
      })
    ];
  };
}
