# nix/services/caddy.nix
{ config, pkgs, lib, ... }:

let
  # Replace with your actual tailnet hostname after `tailscale up`
  tsHostname = "ardent-forge";
  tsDomain = "${tsHostname}.tail1234.ts.net";
in {
  services.caddy = {
    enable = true;

    # Caddy serves all HTTP services behind Tailscale
    virtualHosts = {
      # Ardent Forge UI + API
      "https://${tsDomain}" = {
        extraConfig = ''
          reverse_proxy 127.0.0.1:7030
        '';
      };

      # Grafana
      "https://grafana.${tsDomain}" = {
        extraConfig = ''
          reverse_proxy 127.0.0.1:3000
        '';
      };

      # Prometheus (direct access for debugging)
      "https://prometheus.${tsDomain}" = {
        extraConfig = ''
          reverse_proxy 127.0.0.1:9090
        '';
      };

      # NTFY
      "https://ntfy.${tsDomain}" = {
        extraConfig = ''
          reverse_proxy 127.0.0.1:8090
        '';
      };
    };
  };

  # Allow Caddy to read Tailscale certs
  systemd.services.caddy.serviceConfig.EnvironmentFile = "";
  users.users.caddy.extraGroups = [ "tailscale-cert" ];
}
