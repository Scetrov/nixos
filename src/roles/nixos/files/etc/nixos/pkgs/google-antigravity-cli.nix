{ pkgs }:

pkgs.stdenv.mkDerivation {
  pname = "google-antigravity-cli";
  version = "latest";

  src = pkgs.fetchurl {
    url = "https://antigravity.google/cli/download/linux-amd64";
    # Update with: nix-prefetch-url https://antigravity.google/cli/download/linux-amd64
    sha256 = "0000000000000000000000000000000000000000000000000000";
  };

  dontUnpack = true;

  nativeBuildInputs = [
    pkgs.patchelf
  ];

  installPhase = ''
    runHook preInstall

    mkdir -p $out/bin
    cp $src $out/bin/agy
    chmod +x $out/bin/agy

    runHook postInstall
  '';

  fixupPhase = ''
    runHook preFixup

    patchelf \
      --set-interpreter "$(cat $NIX_CC/nix-support/dynamic-linker)" \
      --set-rpath "${pkgs.stdenv.cc.cc.lib}/lib" \
      $out/bin/agy

    runHook postFixup
  '';
}
