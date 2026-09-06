# nix/services/galley-frontend.nix
#
# Galley's SvelteKit front end, running in dev mode so the work in progress is
# always reachable at https://galley.<tailnet> without someone first starting a
# server over SSH. Caddy proxies that tsnet node to the port pinned here; the
# matching half of the pairing (port + allowedHosts) lives in the repo's
# frontend/vite.config.ts. Galley's local services own 8100-8199; the map is
# in that repo's CLAUDE.md under "Local ports".
{ pkgs, locals, ... }:

{
  systemd.services.galley-frontend = {
    description = "Galley front end — SvelteKit dev server";
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];
    wantedBy = [ "multi-user.target" ];

    serviceConfig = {
      User = locals.username;
      WorkingDirectory = "/home/${locals.username}/Repos/github.com/t-eckert/galley/frontend";
      ExecStart = "${pkgs.pnpm}/bin/pnpm run dev";
      Restart = "on-failure";
      RestartSec = "5s";
      Environment = [
        "HOME=/home/${locals.username}"
        "PATH=${pkgs.pnpm}/bin:${pkgs.nodejs}/bin:/run/current-system/sw/bin"
      ];
    };

    # Dependencies are not installed by this unit: a `pnpm install` that fails
    # (a lockfile mid-edit, no network) would take the dev server down with it.
    # After a dependency change, run `task frontend:install` and restart.
    unitConfig.ConditionPathExists =
      "/home/${locals.username}/Repos/github.com/t-eckert/galley/frontend/node_modules";
  };
}
