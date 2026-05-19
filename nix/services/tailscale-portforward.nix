# nix/services/tailscale-portforward.nix
{ config, pkgs, lib, ... }:

{
  # Redirect all TCP traffic arriving on the Tailscale interface to localhost.
  # This makes any service bound to 127.0.0.1 reachable by port from the tailnet
  # without needing --host flags or per-service Caddy entries.
  # The firewall already trusts tailscale0 (trustedInterfaces); this just bridges
  # the gap between the Tailscale IP (100.x.x.x) and loopback-bound listeners.
  networking.nftables.tables.tailscale-portforward = {
    family = "ip";
    content = ''
      chain prerouting {
        type nat hook prerouting priority dstnat;
        iifname "tailscale0" ip protocol tcp redirect
      }
    '';
  };
}
