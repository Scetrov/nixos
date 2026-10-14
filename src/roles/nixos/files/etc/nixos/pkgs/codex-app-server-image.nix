{ pkgs }:

let
  codexVersion = "0.162.0";
  codexUid = 10001;
  codexGid = 10001;
  nixpkgsRevision = "1c18abadea1a7d275e35a09495fd563c25b75753";
  nixpkgsHash = "1rna5my9cjxna9x60vr2jlxchwrd5xmkqhmvlqwykahyx7sx5qan";
  codexSourceHash = "sha256-YG/9hFOCl4cMYzjaH/3gBid4osxcrvCYQUDDzdbIygo=";
  codexCargoHash = "sha256-UTu+ws1DqL375C+1jaVI9HBqDHnTuAQr7/h1rSzsEzg=";

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
    runtimeInputs = [ pkgs.coreutils ];
    text = ''
      set -euo pipefail
      umask 0007

      test -d "$CODEX_HOME"
      test -d /run/codex-app-server

      # Codex 0.162 uses a private physical socket and an absolute symlink alias.
      # Keep that socket private inside the container; relay the existing shared
      # exporter endpoint rather than exporting a broken container-local symlink.
      server_pid=
      relay_pid=
      # Invoked indirectly by the EXIT trap.
      # shellcheck disable=SC2329
      cleanup() {
        trap - EXIT INT TERM
        if [ -n "$relay_pid" ]; then kill "$relay_pid" 2>/dev/null || true; fi
        if [ -n "$server_pid" ]; then kill "$server_pid" 2>/dev/null || true; fi
        wait || true
      }
      trap cleanup EXIT
      trap 'exit 0' INT TERM

      ${codex}/bin/codex app-server --listen unix:///tmp/codex-private.sock &
      server_pid=$!
      deadline=$((SECONDS + 60))
      until [ -S /tmp/codex-private.sock ]; do
        kill -0 "$server_pid"
        if [ "$SECONDS" -ge "$deadline" ]; then
          echo "Timed out waiting for private Codex socket" >&2
          exit 1
        fi
        sleep 0.1
      done
      ${pkgs.socat}/bin/socat \
        UNIX-LISTEN:/run/codex-app-server/control.sock,mode=0660,fork \
        UNIX-CONNECT:/tmp/codex-private.sock &
      relay_pid=$!
      wait -n "$server_pid" "$relay_pid"
      exit 1
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
