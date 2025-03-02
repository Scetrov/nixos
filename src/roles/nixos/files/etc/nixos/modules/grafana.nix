{ config, lib, ... }:

{
  virtualisation = {
    oci-containers.containers = {
      grafana = {
        image = "grafana/grafana-oss";
        autoStart = true;
        volumes = [
          "grafana-storage:/var/lib/grafana"
        ];
        labels = { 
          "traefik.enable" = "true";

          # HTTPS RPC
          "traefik.http.routers.grafana.rule" = "Host(`grafana.net.scetrov.live`)";
          "traefik.http.routers.grafana.tls" = "true";
          "traefik.http.routers.grafana.entrypoints" = "websecure";
          "traefik.http.routers.grafana.service" = "grafana-service";
          "traefik.http.services.grafana-service.loadbalancer.server.port" = "3000";
        };
      };
    };
  };
}