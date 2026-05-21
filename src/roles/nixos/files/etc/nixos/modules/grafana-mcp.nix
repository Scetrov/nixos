{
  config,
  pkgs,
  lib,
  ...
}:

let
  cfg = config.services.grafana-mcp;
  envFile = "/run/grafana-mcp/env";
in
{
  options.services.grafana-mcp = {
    enable = lib.mkEnableOption "Grafana MCP Server";

    port = lib.mkOption {
      type = lib.types.port;
      default = 8000;
      description = "Internal port for Grafana MCP Server to listen on";
    };

    image = lib.mkOption {
      type = lib.types.str;
      # Default to latest but overridable in host device-configuration for pinning/updates (SR-006)
      default = "docker.io/grafana/mcp-grafana:latest";
      description = "Docker image for the Grafana MCP Server";
    };
  };

  config = lib.mkIf cfg.enable {
    # Reference agenix secret containing the Grafana Service Account token
    age.secrets.grafana_mcp_token.file = /root/secrets/grafana_mcp_token.age;

    virtualisation.oci-containers.containers.grafana-mcp = {
      image = cfg.image;
      autoStart = true;
      ports = [ "127.0.0.1:${toString cfg.port}:8000" ];
      # Run in streamable-http mode with proper endpoint path to support both SSE and Streamable HTTP on a single URL
      cmd = [
        "-t"
        "streamable-http"
        "-endpoint-path"
        "/mcp/sse"
      ];
      environmentFiles = [ envFile ];
      extraOptions = [
        "--add-host=host.containers.internal:host-gateway"
      ];
    };

    systemd.services.podman-grafana-mcp = {
      preStart = ''
        set -euo pipefail
        ${pkgs.coreutils}/bin/install -d -m 0750 -o root -g root /run/grafana-mcp

        mcp_token=$(${pkgs.coreutils}/bin/cat ${config.age.secrets.grafana_mcp_token.path})

        ${pkgs.coreutils}/bin/cat > ${envFile} <<EOF
        GRAFANA_URL=http://host.containers.internal:3005
        GRAFANA_SERVICE_ACCOUNT_TOKEN=$mcp_token
        EOF
        ${pkgs.coreutils}/bin/chmod 0600 ${envFile}
      '';
      serviceConfig = {
        Restart = lib.mkForce "on-failure";
        RestartSec = "10s";
      };
    };
  };
}
