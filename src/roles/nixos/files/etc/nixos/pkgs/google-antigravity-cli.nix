{ pkgs }:

pkgs.stdenv.mkDerivation {
  pname = "google-antigravity-cli";
  version = "1.0.0-5288553236791296";

  src = pkgs.fetchurl {
    url = "https://storage.googleapis.com/antigravity-public/antigravity-cli/1.0.0-5288553236791296/linux-x64/cli_linux_x64.tar.gz";
    sha256 = "sha256-cAljQFdPr8SgbE08gFcxTiLUdc4cgg0K1R/wf7fpnrY=";
  };

  sourceRoot = ".";

  nativeBuildInputs = [
    pkgs.patchelf
  ];

  installPhase = ''
    runHook preInstall

    mkdir -p $out/bin
    cp antigravity $out/bin/agy
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
