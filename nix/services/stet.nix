# nix/services/stet.nix
#
# stet, Galley's development agent. The package and the NixOS module come from
# the galley-agent flake input; its docs/design.md has the reasoning. This file
# only says which of stet's processes run here and how they are fenced.
#
# Two processes for now:
#
#   - The gateway takes webhooks on 127.0.0.1:7410 and hands them to the job
#     that owns them. It routes nothing until its Linear webhook secrets exist
#     (GAL-584), and the Cloudflare Tunnel in front of it comes with them.
#   - The implementer runs one Claude Code session at a time, each in a rootless
#     Podman container, inside the stet-implementer crucible profile below. The
#     containers share the host network and leave only through the profile's
#     proxy. stet-implementer-probe runs `stet probe` in the same slice before
#     every start, so it takes no work unless the fence holds.
#
# Updating stet: pull ~/Repos/github.com/t-eckert/galley-agent, then
#   nix flake update galley-agent --flake /data/ardent-forge/repo/nix
# commit the flake.lock, and af-rebuild. Revert that commit to roll back.
{ config, ... }:

{
  ardentForge.crucible.profiles.stet-implementer = {
    description = "stet's implementer and its session containers";
    # The proxy listens on loopback, and the gateway hands events over it.
    # Loopback also reaches every other local service; nothing on it holds
    # credentials a session could use, and sessions run no database.
    allowLoopback = true;
    allowHosts = [
      "api.anthropic.com"
      # crates.io, index.crates.io and static.crates.io: a bare name covers subdomains.
      "crates.io"
      "registry.npmjs.org"
      # Fetching only. Sessions hold no token; the implementer pushes and opens
      # pull requests with its GitHub App, outside the session.
      "github.com"
      # The implementer's own agent sessions and comments.
      "linear.app"
    ];
    # Matches the unit's own limits, set from galley's measured checks in the
    # stet module, so the slice never cuts in first.
    memoryHigh = "4G";
    memoryMax = "5G";
    verify = {
      mustReach = [ "https://api.anthropic.com/" ];
      mustNotReach = [ "https://api.stripe.com/" ];
    };
  };

  services.stet = {
    implementerProxy = config.ardentForge.crucible.proxyUrls.stet-implementer;
    processes.gateway.enable = true;
    processes.implementer = {
      enable = true;
      serviceConfig.Slice = "crucible-stet-implementer.slice";
    };
  };

  # The implementer's proxy has to be up before its probe runs, which is its own
  # unit, and stays up while the implementer does.
  systemd.services.stet-implementer-probe = {
    requires = [ "crucible-proxy-stet-implementer.service" ];
    after = [ "crucible-proxy-stet-implementer.service" ];
  };
  systemd.services.stet-implementer = {
    requires = [ "crucible-proxy-stet-implementer.service" ];
    after = [ "crucible-proxy-stet-implementer.service" ];
  };
}
