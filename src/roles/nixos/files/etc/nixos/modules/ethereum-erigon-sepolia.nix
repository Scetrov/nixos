{ config, lib, ... }:

{
  users.groups.ethereum = {
    gid = 1001;
  };

  users.users.erigon = {
    isSystemUser = true;
    uid = 101;
    home = "/var/lib/ethereum/erigon/sepolia";
    group = "ethereum";
    shell = "/sbin/nologin";
  };

  environment.etc.erigon-ethereum-sepolia = {
    source = ../../ethereum/erigon/sepolia.toml;
    target = "erigon-ethereum-sepolia.toml";
  };

  systemd.services.setup-erigon-data = {
    script = ''
      mkdir --parents "$ETHEREUM_DATA/erigon/sepolia"
      mkdir --parents "$ETHEREUM_DATA/erigon/sepolia/share"
      chown --recursive erigon:ethereum "$ETHEREUM_DATA"
      find "$ETHEREUM_DATA" -type d -exec chmod 750 {} +
      find "$ETHEREUM_DATA" -type f -exec chmod 640 {} +
    '';
    environment = {
      ETHEREUM_DATA = "/var/lib/ethereum";
    };
    wantedBy = ["multi-user.target"];
    serviceConfig = {
      Type = "oneshot";
    };
  };

  networking.firewall.allowedTCPPorts = [ 30303 30304 42069 ];
  networking.firewall.allowedUDPPorts = [ 30303 30304 42069 ];

  systemd.services.podman-ethereum-erigon-sepolia = {
    wantedBy = [ "multi-user.target" ];
    after = [ "setup-erigon-data.service" ];
    description = "Ethereum Erigon Sepolia Node";
  };

  virtualisation = {
    oci-containers.containers = {
      ethereum-erigon-sepolia = {
        image = "erigontech/erigon:v3.0.0-beta2";
        cmd = [ "--config" "/etc/ethereum/erigon/sepolia.toml" ];
        autoStart = true;
        user = "erigon";
        environment = {
          DOCKER_UID = "101";
          DOCKER_GID = "1001";
          XDG_DATA_HOME = "/var/lib/ethereum/erigon/sepolia/share";
        };
        volumes = [
          "/var/lib/ethereum/erigon/sepolia:/var/lib/ethereum/erigon/sepolia:rw"
          "/var/lib/ethereum/erigon/sepolia/share:/var/lib/ethereum/erigon/sepolia/share:rw"
          "/etc/ethereum/erigon/sepolia.toml:/etc/ethereum/erigon/sepolia.toml:ro"
        ];
        labels = {
          # HTTPS RPC
          "traefik.enable" = "true";
          "traefik.http.routers.ethereum-erigon-sepolia-rpc.rule" = "Host(`rpc.holesky.scetrov.live`)";
          "traefik.http.routers.ethereum-erigon-sepolia-rpc.tls" = "true";
          "traefik.http.routers.ethereum-erigon-sepolia-rpc.entrypoints" = "websecure";
          "traefik.http.routers.ethereum-erigon-sepolia-rpc.service" = "ethereum-erigon-sepolia-rpc-service";
          "traefik.http.services.ethereum-erigon-sepolia-rpc-service.loadbalancer.server.port" = "8454";

          # TCP
          "traefik.tcp.routers.ethereum-erigon-sepolia-snap.entrypoints" = "snap-tcp";
          "traefik.tcp.routers.ethereum-erigon-sepolia-snap.rule" = "HostSNI(`*`)";
          "traefik.tcp.routers.ethereum-erigon-sepolia-snap.service" = "ethereum-erigon-sepolia-snap";
          "traefik.tcp.services.ethereum-erigon-sepolia-snap.loadbalancer.server.port" = "42069";
          "traefik.tcp.routers.ethereum-erigon-sepolia-eth68.entrypoints" = "eth68-tcp";
          "traefik.tcp.routers.ethereum-erigon-sepolia-eth68.rule" = "HostSNI(`*`)";
          "traefik.tcp.routers.ethereum-erigon-sepolia-eth68.service" = "ethereum-erigon-sepolia-eth68";
          "traefik.tcp.services.ethereum-erigon-sepolia-eth68.loadbalancer.server.port" = "30303";
          "traefik.tcp.routers.ethereum-erigon-sepolia-eth67.entrypoints" = "eth67-tcp";
          "traefik.tcp.routers.ethereum-erigon-sepolia-eth67.rule" = "HostSNI(`*`)";
          "traefik.tcp.routers.ethereum-erigon-sepolia-eth67.service" = "ethereum-erigon-sepolia-eth67";
          "traefik.tcp.services.ethereum-erigon-sepolia-eth67.loadbalancer.server.port" = "30304";
          "traefik.tcp.routers.ethereum-erigon-sepolia-sentinel.entrypoints" = "sentinel-tcp";
          "traefik.tcp.routers.ethereum-erigon-sepolia-sentinel.rule" = "HostSNI(`*`)";
          "traefik.tcp.routers.ethereum-erigon-sepolia-sentinel.service" = "ethereum-erigon-sepolia-sentinel";
          "traefik.tcp.services.ethereum-erigon-sepolia-sentinel.loadbalancer.server.port" = "4001";
          
          # UDP
          "traefik.udp.routers.ethereum-erigon-sepolia-snap.entrypoints" = "snap-udp";
          "traefik.udp.routers.ethereum-erigon-sepolia-snap.service" = "ethereum-erigon-sepolia-snap";
          "traefik.udp.services.ethereum-erigon-sepolia-snap.loadbalancer.server.port" = "42069";
          "traefik.udp.routers.ethereum-erigon-sepolia-eth68.entrypoints" = "eth68-udp";
          "traefik.udp.routers.ethereum-erigon-sepolia-eth68.service" = "ethereum-erigon-sepolia-eth68";
          "traefik.udp.services.ethereum-erigon-sepolia-eth68.loadbalancer.server.port" = "30303";
          "traefik.udp.routers.ethereum-erigon-sepolia-eth67.entrypoints" = "eth67-udp";
          "traefik.udp.routers.ethereum-erigon-sepolia-eth67.service" = "ethereum-erigon-sepolia-eth67";
          "traefik.udp.services.ethereum-erigon-sepolia-eth67.loadbalancer.server.port" = "30304";
          "traefik.udp.routers.ethereum-erigon-sepolia-sentinel.entrypoints" = "sentinel-udp";
          "traefik.udp.routers.ethereum-erigon-sepolia-sentinel.service" = "ethereum-erigon-sepolia-sentinel";
          "traefik.udp.services.ethereum-erigon-sepolia-sentinel.loadbalancer.server.port" = "4000";
        };
      };
    };
  };
}