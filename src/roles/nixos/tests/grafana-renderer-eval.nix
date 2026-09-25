{
  pkgs ? import <nixpkgs> { },
}:
let
  lib = pkgs.lib;
  ageStub = { lib, ... }: {
    options.age.secrets = lib.mkOption {
      default = { };
      type = lib.types.attrsOf (
        lib.types.submodule (
          { name, ... }: {
            options = {
              file = lib.mkOption { type = lib.types.path; };
              path = lib.mkOption {
                type = lib.types.str;
                default = "/run/agenix/${name}";
              };
              owner = lib.mkOption {
                type = lib.types.str;
                default = "root";
              };
              group = lib.mkOption {
                type = lib.types.str;
                default = "root";
              };
              mode = lib.mkOption {
                type = lib.types.str;
                default = "0400";
              };
            };
          }
        )
      );
    };
  };
  config =
    (import <nixpkgs/nixos/lib/eval-config.nix> {
      system = "x86_64-linux";
      modules = [
        ageStub
        ../files/etc/nixos/modules/grafana.nix
        { system.stateVersion = "26.05"; }
      ];
    }).config;
  environmentFile = config.age.secrets.grafana_renderer_environment.path;
in
assert lib.assertMsg (
  config.services.grafana-image-renderer.enable
  && config.services.grafana-image-renderer.settings.server.addr == "127.0.0.1:18081"
  && config.services.grafana.settings.rendering.server_url == "http://127.0.0.1:18081/render"
  &&
    config.services.grafana.settings.rendering.callback_url
    == "https://metrics.net.scetrov.live/grafana/"
  && config.services.grafana.settings.rendering.concurrent_render_request_limit == 1
) "renderer must remain loopback-only and callback through the Grafana subpath";
assert lib.assertMsg (
  environmentFile == "/run/agenix/grafana_renderer_environment"
  && builtins.elem environmentFile config.systemd.services.grafana.serviceConfig.EnvironmentFile
  && config.systemd.services.grafana-image-renderer.serviceConfig.EnvironmentFile == environmentFile
  && config.age.secrets.grafana_renderer_environment.mode == "0400"
  && !(builtins.hasAttr "renderer_token" config.services.grafana.settings.rendering)
) "renderer authentication must come from a runtime-injected encrypted secret, not the Nix store";
pkgs.writeText "grafana-renderer-eval-passed" "PASS"
