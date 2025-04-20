{ config, ... }:

{
  services.openvpn.servers = {
    nordVPN = { config = '' config /root/vpn/uk1898.nordvpn.com.udp.ovpn ''; };
  };
}
