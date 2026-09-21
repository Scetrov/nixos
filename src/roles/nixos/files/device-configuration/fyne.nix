{
  config,
  lib,
  pkgs,
  ...
}:

{
  imports = [
    "${
      builtins.fetchTarball {
        url = "https://github.com/NixOS/nixos-hardware/archive/9ebcb7766700d7e006d9505247bd7ce0426f4232.tar.gz";
        sha256 = "185wfiqdw4aa8pf4k2qrxnakmi4r4klyk9x3jxzgd97m7dm5g10l";
      }
    }/raspberry-pi/4"
    ./modules/blocky.nix
    ./modules/bootstrap-dns.nix
    ./modules/local-networking.nix
    ./modules/user-scetrov-syncthing.nix
  ];

  # The downstream Raspberry Pi kernel is not available from the NixOS binary
  # cache and takes over an hour to compile on Fyne. The hardware module permits
  # any kernel >= 6.1; use the cached generic aarch64 kernel from this channel.
  boot.kernelPackages = pkgs.linuxPackages;

  # During a kernel transition, systemd-sysctl runs against the booted kernel
  # but NixOS derives these maxima from the new kernel. A leading dash keeps an
  # unsupported target value from failing activation; it is applied after reboot.
  environment.etc."sysctl.d/55-nixos-aslr-entropy.conf".source = lib.mkForce (
    pkgs.runCommand "55-nixos-aslr-entropy-tolerant.conf"
      {
        inherit (config.boot.kernelPackages.kernel) configfile;
      }
      ''
        mmap_rnd_bits_max=$(grep '^CONFIG_ARCH_MMAP_RND_BITS_MAX=' "$configfile" | grep --only-matching '[0-9]*$')
        mmap_rnd_compat_bits_max=$(grep '^CONFIG_ARCH_MMAP_RND_COMPAT_BITS_MAX=' "$configfile" | grep --only-matching '[0-9]*$')
        test -n "$mmap_rnd_bits_max"
        test -n "$mmap_rnd_compat_bits_max"
        printf '%s\n' \
          "-vm.mmap_rnd_bits=$mmap_rnd_bits_max" \
          "-vm.mmap_rnd_compat_bits=$mmap_rnd_compat_bits_max" > "$out"
      ''
  );

  blocky.bindAddr = "10.229.53.1:53";

  networking = {
    networkmanager = {
      enable = true;
      plugins = [ pkgs.networkmanager-openvpn ];
    };
    hostName = "fyne";
    defaultGateway = "10.229.0.1";
    interfaces.eth0.ipv4.addresses = [
      {
        address = "10.229.10.1";
        prefixLength = 16;
      }
      {
        address = "10.229.53.1";
        prefixLength = 16;
      }
    ];
  };
}
