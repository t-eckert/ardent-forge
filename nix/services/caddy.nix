# nix/services/caddy.nix
{ config, pkgs, lib, locals, ... }:

let
  tsDomain = locals.tailnetDomain;
  # "ardent-forge.feist-gondola.ts.net" -> "feist-gondola.ts.net"
  tailnet = lib.concatStringsSep "." (builtins.tail (lib.splitString "." tsDomain));

  # Per-app tsnet nodes registered via the caddy-tailscale plugin. Each
  # shows up as its own machine in the tailnet admin console with an
  # auto-issued cert at <name>.<tailnet>.
  csApps = {
    cs         = { backend = "127.0.0.1:8000"; };  # chillest-subs
    cs-editor  = { backend = "127.0.0.1:8010"; };  # chill-subs editor
    cs-grafana = { backend = "127.0.0.1:8022"; };  # podman: local_grafana_1
    cs-galley  = { backend = "127.0.0.1:8020"; };  # galley backend
    lab        = { backend = "127.0.0.1:2718"; };  # marimo notebooks
    te         = { backend = "127.0.0.1:10000"; }; # thomaseckert.dev
  };

  csNodeBlock = lib.concatStringsSep "\n  " (lib.mapAttrsToList
    (name: _: "${name} { hostname ${name} }") csApps);

  csVirtualHosts = lib.mapAttrs' (name: { backend, ... }:
    lib.nameValuePair "${name}.${tailnet}" {
      extraConfig = ''
        bind tailscale/${name}
        reverse_proxy ${backend}
      '';
    }) csApps;
in {
  services.caddy = {
    enable = true;

    # Bake in the caddy-tailscale plugin so each cs* vhost can register as
    # its own tsnet node. First build will fail with a hash mismatch; paste
    # the suggested sha256 in place of lib.fakeHash and rebuild.
    package = pkgs.caddy.withPlugins {
      plugins = [
        "github.com/tailscale/caddy-tailscale@v0.0.0-20260106222316-bb080c4414ac"
      ];
      hash = "sha256-XBdYjtuPVu/beIgFgFcVp6ln4r9kq0B6+4xJ8+WWYn0=";
    };

    # Tailscale credential lives in /etc/caddy/tailscale-auth (root:caddy
    # 0640) as TS_AUTHKEY. The plugin accepts an OAuth client secret in
    # place of a regular auth key — it auto-mints per-node keys from the
    # OAuth secret as long as the right tag is declared (below).
    environmentFile = "/etc/caddy/tailscale-auth";

    globalConfig = ''
      tailscale {
        auth_key {env.TS_AUTHKEY}
        tags tag:cs-caddy

        ${csNodeBlock}
      }
    '';

    virtualHosts = {
      # Existing: Ardent Forge UI + path-based service exposure. Binds to
      # the host's tailscale0 interface and uses certs fetched via tailscaled
      # (caddy is in the tailscale-cert group, below).
      "https://${tsDomain}" = {
        extraConfig = ''
          handle /svc/grafana* {
            reverse_proxy 127.0.0.1:3000
          }
          handle_path /svc/prometheus* {
            reverse_proxy 127.0.0.1:9090
          }
          handle_path /svc/ntfy* {
            reverse_proxy 127.0.0.1:8090
          }

          handle {
            reverse_proxy 127.0.0.1:7030
          }
        '';
      };
    } // csVirtualHosts;

    # NixOS default is `level ERROR`, which swallows the tsnet startup logs
    # we need to see while bringing up the cs* nodes. Bump to INFO so the
    # plugin's "registering with control" / "got cert" lines show up in
    # journalctl -u caddy.
    logFormat = lib.mkForce "level INFO";
  };

  # tsnet does an OAuth handshake + control plane registration for each of
  # the four cs* nodes at startup. The NixOS unit's default 90s
  # TimeoutStartSec isn't enough for that on a cold start; give it room.
  systemd.services.caddy.serviceConfig.TimeoutStartSec = "5min";

  # Allow Caddy to read Tailscale certs (still needed for the ardent-forge
  # host; the cs* hosts get their certs through tsnet directly).
  users.users.caddy.extraGroups = [ "tailscale-cert" ];
}
