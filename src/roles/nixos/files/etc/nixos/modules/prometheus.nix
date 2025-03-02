{ config, lib, ... }:

{
  environment.etc.prometheus-config = {
    source = ../../prometheus/prometheus.yml;
    target = "prometheus/prometheus.yml";
  };

  services.prometheus = {
    exporters = {
      node = {
        enable = true;
        enabledCollectors = [ "systemd" ];
        port = 9100;
      };
    };
  };

  virtualisation = {
    oci-containers.containers = {
      prometheus = {
        image = "prom/prometheus";
        autoStart = true;
        volumes = [
          "/etc/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro"
          "prometheus-data:/prometheus:rw"
        ];
        labels = { 
          "traefik.enable" = "true";

          # HTTPS RPC
          "traefik.http.routers.prometheus.rule" = "Host(`prometheus.net.scetrov.live`)";
          "traefik.http.routers.prometheus.tls" = "true";
          "traefik.http.routers.prometheus.entrypoints" = "websecure";
          "traefik.http.routers.prometheus.service" = "prometheus-service";
          "traefik.http.services.prometheus-service.loadbalancer.server.port" = "9090";
        };
        extraOptions = [
          "--add-host=host.podman.internal:host-gateway"
        ];
      };
    };
  };
}