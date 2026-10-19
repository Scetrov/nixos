# No production secrets or host activation; includes official schema validation.
{
  enable ? true,
  appId ? 123,
  installationIds ? [
    111
    222
  ],
}:
let
  pkgs = import <nixpkgs> { };
  lib = pkgs.lib;
  evaluated = import <nixpkgs/nixos/lib/eval-config.nix> {
    system = "x86_64-linux";
    modules = [
      ../src/roles/nixos/files/etc/nixos/modules/github-sbom-collector.nix
      ({ lib, ... }: {
        options.age.secrets = lib.mkOption {
          type = lib.types.attrs;
          default = { };
        };
        config = {
          system.stateVersion = "26.05";
          users.groups.alloy = { };
          scetrov.services.github-sbom-collector = {
            inherit enable;
            githubAppId = appId;
            githubInstallationIds = installationIds;
            sources = [
              {
                repository = "Scetrov/efctl";
                repositoryId = 1166984576;
                workflowId = 238717662;
                project = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
              }
            ];
          };
        };
      })
    ];
  };
  cfg = evaluated.config;
  service = cfg.systemd.services.github-sbom-collector.serviceConfig;
  schemas = builtins.elemAt (lib.splitString " " service.ExecStart) 5;
in
{
  enabled = builtins.hasAttr "github-sbom-collector" cfg.systemd.services;
  timer = if enable then cfg.systemd.timers.github-sbom-collector.timerConfig else { };
  credentials = if enable then service.LoadCredential else [ ];
  failedAppAssertions = map (a: a.message) (
    builtins.filter (a: !a.assertion && lib.hasPrefix "SBOM collection" a.message) cfg.assertions
  );
  sandbox =
    if enable then
      {
        inherit (service)
          User
          StateDirectoryMode
          ProtectSystem
          TimeoutStartSec
          MemoryMax
          ;
      }
    else
      { };
  check =
    pkgs.runCommand "github-sbom-collector-tests"
      {
        nativeBuildInputs = [
          (pkgs.python3.withPackages (ps: [
            ps.jsonschema
            ps.cryptography
          ]))
        ];
      }
      ''
        mkdir -p scripts/tests src/roles/nixos/files/etc/nixos/pkgs
        cp ${../scripts/tests/test_github_sbom_collector.py} scripts/tests/test_github_sbom_collector.py
        cp ${../scripts/tests/test_github_sbom_app.py} scripts/tests/test_github_sbom_app.py
        cp ${../scripts/tests/run_github_sbom_upload_integration.py} scripts/tests/run_github_sbom_upload_integration.py
        cp ${../src/roles/nixos/files/etc/nixos/pkgs/github-sbom-collector.py} src/roles/nixos/files/etc/nixos/pkgs/github-sbom-collector.py
        export SBOM_SCHEMA_DIR=${schemas}
        export PYTHONDONTWRITEBYTECODE=1
        python3 -m unittest scripts.tests.test_github_sbom_collector scripts.tests.test_github_sbom_app
        touch "$out"
      '';
}
