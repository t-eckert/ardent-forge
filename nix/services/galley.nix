# nix/services/galley.nix
#
# Galley's local development environment is **not** managed by this box any
# more. It is one process-compose stack in the Galley repo — `task dev:up`,
# `task dev:down`, `process-compose.yaml` at that repo's root — started by
# whoever is working and stopped when they are done.
#
# This file held four units until 9 September 2026: `galley-frontend` and
# `galley-storybook` running pnpm out of the working tree, `galley-deps`
# restarting both when an install finished, and a root `galley-postgres`
# container on /data/galley-postgres. They came up with the box and were never
# stopped, and that turned out to be the problem rather than the convenience:
#
#   - A service that is always up is never *brought* up, so nothing ever ran
#     the path a fresh checkout takes. On the day this was removed the front
#     end had been answering 500 to every request for days — `SERVICE_TOKEN`
#     was unset and nothing had restarted it since that started mattering.
#   - The database container ran as root against a directory this box also
#     managed with a tmpfiles rule, and the two disagreed about ownership. The
#     port answered and the postmaster was up while every single connection
#     died with `could not open file "global/pg_filenode.map": Permission
#     denied`. The rootless podman volume that replaced it has no such seam.
#   - A unit owns its port whether or not anyone is working, so running a dev
#     server by hand meant `sudo systemctl stop` first.
#
# **Do not put them back.** If Galley needs something from this box it is a
# reverse-proxy route in caddy.nix or a scrape target in monitoring.nix, both
# of which already exist and both of which tolerate the backend being down.
#
# /data/galley-postgres is left on disk, unmanaged and unused. Delete it when
# you are sure nothing in it is wanted; the new volume is `galley-pgdata`,
# owned by the user, and `task dev:db:reset` is how it gets thrown away.
{ ... }:

{ }
