{ pkgs }:

let
  codexVersion = "0.145.0";
  codexUid = 10001;
  codexGid = 10001;
  nixpkgsRevision = "9bc02893134c733dd85de46ee4fb2fac696b5529";
  nixpkgsHash = "1850ky2d8lvv2m60grz5dlfr4d03s4b6kj4vbpba7lff0hlvg13s";
  codexSourceHash = "sha256-/r4mBoJhHB1v5NTA4Hk565/D5B0deYJf9xJW330hyf0=";
  codexCargoHash = "sha256-t9IMRK9R+Z67ThEcgBI0HQU0E4aJHcOjKp22RFclh9U=";

  pinnedNixpkgs = builtins.fetchTarball {
    url = "https://github.com/NixOS/nixpkgs/archive/${nixpkgsRevision}.tar.gz";
    sha256 = nixpkgsHash;
  };
  codexPkgs = import pinnedNixpkgs {
    system = pkgs.stdenv.hostPlatform.system;
    config.allowUnfree = true;
  };
  codexPackageText = builtins.readFile "${pinnedNixpkgs}/pkgs/by-name/co/codex/package.nix";
  codex = codexPkgs.codex;
  entrypoint = pkgs.writeShellApplication {
    name = "codex-app-server-entrypoint";
    text = ''
      set -euo pipefail
      umask 0007

      test -d "$CODEX_HOME"
      test -d /run/codex-app-server

      exec ${codex}/bin/codex app-server \
        --listen unix:///run/codex-app-server/control.sock
    '';
  };
in
assert pkgs.lib.assertMsg (
  builtins.match "[0-9a-f]{40}" nixpkgsRevision != null
) "Codex image Nixpkgs input must use an immutable 40-character revision";
assert pkgs.lib.assertMsg (
  builtins.match "[0-9a-df-np-sv-z0-9]{52}" nixpkgsHash != null
) "Codex image Nixpkgs input must include a valid fixed-output hash";
assert pkgs.lib.assertMsg (
  codex.version == codexVersion
) "Unexpected Codex version ${codex.version}; expected ${codexVersion}";
assert pkgs.lib.assertMsg (
  codex.src.rev == "refs/tags/rust-v${codexVersion}"
) "Codex source must use the pinned official release tag";
assert pkgs.lib.assertMsg (
  codex.src.outputHash == codexSourceHash
) "Codex source integrity hash differs from the reviewed value";
assert pkgs.lib.assertMsg (pkgs.lib.hasInfix ''cargoHash = "${codexCargoHash}"'' codexPackageText)
  "Codex dependency integrity hash is missing or differs from the reviewed value";
assert pkgs.lib.assertMsg (
  !pkgs.lib.hasInfix "latest" codexVersion
) "Codex image tag must not be floating";
pkgs.dockerTools.buildLayeredImage {
  name = "codex-app-server";
  tag = codexVersion;
  created = "1970-01-01T00:00:01Z";

  contents = [
    codex
    entrypoint
    pkgs.cacert
  ];

  fakeRootCommands = ''
    mkdir -p ./etc ./var/empty
    cat > ./etc/passwd <<'EOF'
    codex-app-server:x:${toString codexUid}:${toString codexGid}:Codex app-server:/var/empty:/sbin/nologin
    EOF
    cat > ./etc/group <<'EOF'
    codex-app-server:x:${toString codexGid}:
    EOF
    chmod 0644 ./etc/passwd ./etc/group
    chmod 0555 ./var/empty
  '';

  config = {
    User = "${toString codexUid}:${toString codexGid}";
    Entrypoint = [ "${entrypoint}/bin/codex-app-server-entrypoint" ];
    Env = [
      "CODEX_HOME=/var/lib/codex-app-server"
      "LOG_FORMAT=json"
      "RUST_LOG=warn"
      "RUST_BACKTRACE=0"
      "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
      "NIX_SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
    ];
    Labels = {
      "org.opencontainers.image.source" = "https://github.com/openai/codex";
      "org.opencontainers.image.version" = codexVersion;
      "org.opencontainers.image.revision" = "rust-v${codexVersion}";
    };
  };
}
