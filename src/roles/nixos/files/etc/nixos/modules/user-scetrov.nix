{ config, pkgs, ... }:
let
  baseconfig = {
    allowUnfree = true;
  };
  unstable = import <nixos-unstable> { config = baseconfig; };
in
{
  age.secrets.user_password_hashed.file = /root/secrets/user_password_hashed.age;

  nix.settings.trusted-users = [
    "root"
    "scetrov"
  ];
  users.users.scetrov = {
    isNormalUser = true;
    description = "scetrov";
    hashedPasswordFile = config.age.secrets.user_password_hashed.path;
    extraGroups = [
      "networkmanager"
      "wheel"
      "docker"
      "plugdev"
    ];
    openssh.authorizedKeys.keys = [
      "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDB7n7NyXkm6OucNqS9ExJPUJk/+jhcIxTJD3RnEt2IywDvHWUOBBEcfpOxprj54UsJDrfAslIvhFZkjEi+3Tgow1qC7+HVS3GfNu1YCP+MmTOnnEXgAhtaM7LTVFgt9QYEZeSpgrIIaKSlb515ln4Ghy+Jehbs06V6TcJYG/qIQd1RXN40O13VEyXmNAVRSf9ra7Emfg1OLzu7wabhxLqeLGBJ2cf0QKf0+ip+jYqbq/D2ZsCBYmGgQcKiopuCW7a51zzu/Df6G+SJS2yzWwZx1PjJ0yqUFWpuVDlRJi2sBbBTL1TUftMzRiZsyQPrS/eAlGLxzGjmvjzZ3pLZtD5xc6Qs7By/r/5Acxbp+2wn3fuo6lVmD5P54R0PsQyw7jrV7C7Zb7Cl7EuXZqW3Pm42aowq4skstTmdXsZZx0RkFvFaxDw5IFtC78E5Dwy/4pECLNXQ8stc6A5MKElGwHhcABK8IdUGf6R0lU4yEzknb7KhvERZRKEslQh3Jcn+7zScc5WBbjT3SMEdySWPMwreOpe1gnt+6MSf/8lpQCyBOP1Mr4/SSa95pJpWyRr1OSPi0KgOvSTVwppG6thcV1fRpGsDtpPB192KKrzInP3fxF0UOT3PhLgn7zZAlyGBAIel4m/zK0tqjL3kG2CNwnOkMrq5CTdK1JS7KnK4a/rxCw=="
    ];
    shell = pkgs.zsh;
    packages = with pkgs; [
      btop
      curl
      fzf
      git
      go
      lsb-release
      nixfmt-rfc-style
      nmap
      powershell
      rustup
      tmux
      unstable.chezmoi
      unstable.devenv
      unstable.dotnetCorePackages.sdk_9_0-bin
      unstable.foundry
      unstable.ghostty
      unstable.hugo
      unstable.oh-my-posh
      unstable.gitleaks
      usbutils
    ];
  };
}
