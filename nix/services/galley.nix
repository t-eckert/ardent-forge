# nix/services/galley.nix
#
# Galley's local development services. Galley owns 8100-8199 on this box; the
# map lives in that repo's CLAUDE.md under "Local ports".
#
# The two node processes run straight out of the working tree, so they pick up
# edits on their own — a rebuild here is only needed when this file changes.
{ pkgs, locals, ... }:

let
  repo = "/home/${locals.username}/Repos/github.com/t-eckert/galley";

  # Dependencies are deliberately not installed by these units: a `pnpm
  # install` that failed on a half-edited lockfile or a dead network would take
  # the server down with it. They are conditioned on node_modules existing
  # instead, so after a dependency change run `task frontend:install` and
  # restart. A unit whose condition fails goes inactive quietly rather than
  # entering a restart loop.
  pnpmService = { description, dir, script }: {
    inherit description;
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];
    wantedBy = [ "multi-user.target" ];

    unitConfig.ConditionPathExists = "${dir}/node_modules";

    serviceConfig = {
      User = locals.username;
      WorkingDirectory = dir;
      ExecStart = "${pkgs.pnpm}/bin/pnpm run ${script}";
      Restart = "on-failure";
      RestartSec = "5s";
      Environment = [
        "HOME=/home/${locals.username}"
        "PATH=${pkgs.pnpm}/bin:${pkgs.nodejs}/bin:/run/current-system/sw/bin"
      ];
    };
  };
in
{
  # The app, on the tailnet as `galley`. Port and allowedHosts are pinned in
  # the repo's frontend/vite.config.ts; Caddy proxies the node to it.
  systemd.services.galley-frontend = pnpmService {
    description = "Galley front end — SvelteKit dev server (:8100)";
    dir = "${repo}/frontend";
    script = "dev";
  };

  # Its own tsnet node rather than a path on the app's, because Storybook asks
  # for its assets from an absolute root — the reason ntfy could not live under
  # a prefix either. Storybook runs a Host header check of its own and needs
  # the tailnet name in `core.allowedHosts` in .storybook/main.ts.
  systemd.services.galley-storybook = pnpmService {
    description = "Galley Storybook (:8160)";
    dir = "${repo}/frontend";
    script = "storybook";
  };

  # The dev database gets its own container rather than a database on this
  # box's Postgres: it stays disposable against migrations, it pins its version
  # independently of the host cluster, and it stays out of the nightly pg_dump
  # in postgresql.nix, which dumps every non-template database it finds.
  #
  # Digest-pinned for the reason given in ntfy.nix and the-weather.nix: a tag
  # re-resolves on every start, so what runs here could change across a reboot
  # with nothing in this repo to show for it. postgres:17-alpine as of
  # 2026-09-06, which is 17.11. Resolve a new one with
  # `podman pull docker.io/library/postgres:17-alpine` and read RepoDigests.
  virtualisation.oci-containers.containers.galley-postgres = {
    image = "docker.io/library/postgres@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73";
    autoStart = true;

    ports = [ "127.0.0.1:8120:5432" ];
    volumes = [ "/data/galley-postgres:/var/lib/postgresql/data" ];

    environment = {
      POSTGRES_USER = "galley";
      POSTGRES_DB = "galley";
      TZ = "America/Toronto";

      # Trust auth rather than a password. The port is bound to loopback only —
      # not to tailscale0 — so nothing off this box can reach it, and this way
      # there is no dev credential to commit here or to rotate later. Anything
      # running on the box can connect, which is the trade and is fine for a
      # single-user machine.
      POSTGRES_HOST_AUTH_METHOD = "trust";
    };
  };

  # The image's entrypoint starts as root and chowns PGDATA to its own postgres
  # user, so this only has to exist.
  systemd.tmpfiles.rules = [
    "d /data/galley-postgres 0750 root root -"
  ];
}
