# nix/services/caddy.nix
{ config, pkgs, lib, locals, ... }:

let
  tsDomain = locals.tailnetDomain;
in {
  services.caddy = {
    enable = true;

    # Caddy serves all HTTP services behind Tailscale
    virtualHosts = {
      "https://${tsDomain}" = {
        extraConfig = ''
          # Services under /svc/
          handle /svc/grafana* {
            reverse_proxy 127.0.0.1:3000
          }
          handle_path /svc/prometheus* {
            reverse_proxy 127.0.0.1:9090
          }
          handle_path /svc/ntfy* {
            reverse_proxy 127.0.0.1:8090
          }

          # Everything else → Ardent Forge UI + API
          handle {
            reverse_proxy 127.0.0.1:7030
          }
        '';
      };
    };
  };

  # Allow Caddy to read Tailscale certs
  systemd.services.caddy.serviceConfig.EnvironmentFile = "";
  users.users.caddy.extraGroups = [ "tailscale-cert" ];
}
