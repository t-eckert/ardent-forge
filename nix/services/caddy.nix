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
  #
  # `label` is the human-readable name on the landing page below, which is
  # generated from this same attrset — adding a host here is all it takes to
  # get it listed.
  csApps = {
    cs         = { backend = "127.0.0.1:8000";  label = "chillest-subs"; };
    cs-editor  = { backend = "127.0.0.1:8010";  label = "chill-subs editor"; };
    cs-galley  = { backend = "127.0.0.1:8020";  label = "Galley backend"; };
    galley     = { backend = "127.0.0.1:8100";  label = "Galley (dev server)"; };
    lab        = { backend = "127.0.0.1:2718";  label = "marimo notebooks"; };
    notes      = { backend = "127.0.0.1:8040";  label = "csg planning notes"; };
    # Its own node rather than a /svc path: ntfy's web app requests its assets
    # from an absolute /static, so under handle_path (which strips the prefix)
    # every asset 404'd against the landing page's file_server. The shell
    # returned 200 and then died, which is why nothing was ever subscribed.
    ntfy       = { backend = "127.0.0.1:8090";  label = "push notifications"; };
    te         = { backend = "127.0.0.1:10000"; label = "thomaseckert.dev"; };
    weather    = { backend = "127.0.0.1:8091";  label = "the weather"; };
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

  # Landing page for the bare tailnet domain. This used to reverse-proxy the
  # Ardent Forge web UI on :7030; with that gone, the root is just a directory
  # of what the box is running, generated from the definitions above so it
  # can't drift out of sync.
  appRows = lib.concatStringsSep "\n" (lib.mapAttrsToList (name: attrs: ''
            <li><a href="https://${name}.${tailnet}"><b>${name}</b><span>${attrs.label}</span></a></li>'') csApps);

  landingPage = pkgs.writeTextDir "index.html" ''
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>ardent forge</title>
      <style>
        :root {
          --bg: #fbfaf8; --fg: #17150f; --dim: #6d675c;
          --line: #e3ded4; --card: #ffffff; --accent: #9a3412;
        }
        @media (prefers-color-scheme: dark) {
          :root {
            --bg: #14130f; --fg: #ece7dd; --dim: #8d8677;
            --line: #2b2822; --card: #1c1a15; --accent: #f0a068;
          }
        }
        * { box-sizing: border-box; }
        body {
          margin: 0; padding: 3rem 1.5rem 5rem; background: var(--bg); color: var(--fg);
          font: 15px/1.5 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
          -webkit-font-smoothing: antialiased;
        }
        main { max-width: 46rem; margin: 0 auto; }
        h1 {
          margin: 0; font-size: 1.4rem; font-weight: 600; letter-spacing: -0.02em;
        }
        .sub { margin: 0.35rem 0 2.75rem; color: var(--dim); font-size: 0.875rem; }
        .sub code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
        h2 {
          margin: 2.25rem 0 0.75rem; font-size: 0.7rem; font-weight: 600;
          letter-spacing: 0.1em; text-transform: uppercase; color: var(--dim);
        }
        ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.4rem; }
        a {
          display: flex; align-items: baseline; gap: 0.75rem; padding: 0.7rem 0.9rem;
          background: var(--card); border: 1px solid var(--line); border-radius: 8px;
          text-decoration: none; color: inherit;
        }
        a:hover { border-color: var(--accent); }
        a b {
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-weight: 500; font-size: 0.875rem;
        }
        a span { color: var(--dim); font-size: 0.8125rem; margin-left: auto; text-align: right; }
        footer { margin-top: 3.5rem; color: var(--dim); font-size: 0.8125rem; }
      </style>
    </head>
    <body>
      <main>
        <h1>ardent forge</h1>
        <p class="sub">NixOS box on <code>${tailnet}</code>. Config lives at
          <code>/data/ardent-forge/repo</code>.</p>

        <h2>Apps</h2>
        <ul>
    ${appRows}
        </ul>

        <h2>Services</h2>
        <ul>
          <li><a href="/svc/grafana/"><b>grafana</b><span>dashboards &amp; logs</span></a></li>
          <li><a href="/svc/prometheus/"><b>prometheus</b><span>metrics</span></a></li>
        </ul>

        <h2>Files</h2>
        <ul>
          <li><a href="https://${shareName}.${tailnet}"><b>${shareName}</b><span>WebDAV share — mount from Finder with &#8984;K</span></a></li>
        </ul>

        <footer>Everything here is tailnet-only. Nothing is exposed publicly.</footer>
      </main>
    </body>
    </html>
  '';
in {
  services.caddy = {
    enable = true;

    # Bake in the caddy-tailscale plugin so each cs* vhost can register as
    # its own tsnet node. First build will fail with a hash mismatch; paste
    # the suggested sha256 in place of lib.fakeHash and rebuild.
    package = pkgs.caddy.withPlugins {
      plugins = [
        "github.com/tailscale/caddy-tailscale@v0.0.0-20260826180304-de41b249af4f"
        "github.com/mholt/caddy-webdav@v0.0.0-20260127042217-fa2f366b0d75"
      ];
      # Combined module hash for the tailscale + webdav plugin set. If you add
      # or bump a plugin, set this to lib.fakeHash, rebuild, and paste the
      # suggested sha256 the build prints.
      hash = "sha256-teTBXms3+kot4hTi8wb/NRZPk7A9oSGFhwUbo/COeBo=";
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
      # Landing page + path-based service exposure. Binds to the host's
      # tailscale0 interface and uses certs fetched via tailscaled (caddy is
      # in the tailscale-cert group, below).
      "https://${tsDomain}" = {
        extraConfig = ''
          handle /svc/grafana* {
            reverse_proxy 127.0.0.1:3000
          }
          handle_path /svc/prometheus* {
            reverse_proxy 127.0.0.1:9090
          }
          handle {
            root * ${landingPage}
            file_server
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
