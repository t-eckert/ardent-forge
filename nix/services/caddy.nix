# nix/services/caddy.nix
{ config, pkgs, lib, locals, ... }:

let
  tsDomain = locals.tailnetDomain;
  # "ardent-forge.feist-gondola.ts.net" -> "feist-gondola.ts.net"
  tailnet = lib.concatStringsSep "." (builtins.tail (lib.splitString "." tsDomain));

  # WebDAV drop folder, its own tsnet node at <shareName>.<tailnet>. Mount it
  # from a Mac via Finder (⌘K -> https://drop.<tailnet>) to drag files onto the
  # box; Claude Code sessions read them out of shareDir via the screenshots skill.
  shareName = "drop";
  shareDir = "/var/lib/shared";

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

  csVirtualHosts = lib.mapAttrs' (name: attrs:
    lib.nameValuePair "${name}.${tailnet}" {
      extraConfig = ''
        bind tailscale/${name}
        ${attrs.routes or "reverse_proxy ${attrs.backend}"}
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
        "github.com/mholt/caddy-webdav@v0.0.0-20260127042217-fa2f366b0d75"
      ];
      # Combined module hash for the tailscale + webdav plugin set. If you add
      # or bump a plugin, set this to lib.fakeHash, rebuild, and paste the
      # suggested sha256 the build prints.
      hash = "sha256-UMo8iRQ2trovzSfnb0a2bEGwse32FCN+hpR6kHTyo7c=";
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
        ${shareName} { hostname ${shareName} }
      }

      # webdav isn't a standard directive, so it needs an explicit slot in the
      # handler order. Pair it with file_server for the drop share.
      order webdav before file_server
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
      # WebDAV drop folder as its own tsnet node. No auth — reachable only
      # from the tailnet. Mount from a Mac via Finder (⌘K).
      "${shareName}.${tailnet}" = {
        extraConfig = ''
          bind tailscale/${shareName}
          root * ${shareDir}
          webdav
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

  # Shared drop folder that Caddy's WebDAV handler writes into. Owned by
  # caddy but group `users` + setgid (2775) so files land group-readable and
  # thomaseckert (member of `users`) can read them from Claude Code sessions.
  # /var/lib is writable under ProtectSystem=full, so no ReadWritePaths tweak.
  systemd.tmpfiles.rules = [
    "d ${shareDir} 2775 caddy users -"
  ];
}
