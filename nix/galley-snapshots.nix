# nix/galley-snapshots.nix
#
# Once a week, photograph every page of Galley as it stands on origin/dev and
# file the week in the gallery Caddy serves at galley-snapshots.<tailnet>.
#
# The work is galley's tools/snapshots/run.py: it builds a throwaway stack from
# a clean checkout in a podman pod, the way `task ci` does, shoots the pages,
# compares them with last week's and tears the stack down. Nothing here is a
# standing dev stack, which galley's DEV_STACK.md forbids.
#
# A user unit because rootless podman, the cargo cache and the CI checkout all
# belong to this user. Lingering is enabled, so it runs without anyone logged
# in. It runs the script from the main galley checkout and shares local CI's
# lock, so a run that lands during `task ci` waits for it to finish.
{ config, pkgs, lib, locals, ... }:

let
  tailnet = lib.concatStringsSep "." (builtins.tail (lib.splitString "." locals.tailnetDomain));
  galley = "${config.home.homeDirectory}/Repos/github.com/t-eckert/galley";
in
{
  systemd.user.services.galley-snapshots = {
    Unit = {
      Description = "Photograph every page of Galley on dev";
      After = [ "network-online.target" ];
    };
    Service = {
      Type = "oneshot";
      # A user unit sources no login shell. /run/wrappers/bin carries the
      # setuid newuidmap rootless podman needs; the profile carries the rest.
      Environment = [
        "PATH=/run/wrappers/bin:/etc/profiles/per-user/${config.home.username}/bin:/run/current-system/sw/bin"
        "PLAYWRIGHT_BROWSERS_PATH=${pkgs.playwright-driver.browsers}"
        "PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=true"
      ];
      WorkingDirectory = galley;
      ExecStart = lib.escapeShellArgs [
        "${pkgs.python3}/bin/python3" "${galley}/tools/snapshots/run.py"
        "--out" "/data/galley-snapshots"
        "--notify" "http://127.0.0.1:8090/galley-snapshots"
        "--url" "https://galley-snapshots.${tailnet}"
        "--wait"
      ];
      # A cold run builds the API from scratch; a warm one takes about five
      # minutes. The cap only stops a wedged run from holding the timer.
      TimeoutStartSec = "90min";
      Nice = 10;
    };
  };

  systemd.user.timers.galley-snapshots = {
    Unit.Description = "Weekly Galley UI snapshots";
    Timer = {
      # Sunday evening, clear of the Monday 00:00 nix-gc. Persistent catches
      # up a run missed while the box was down.
      OnCalendar = "Sun *-*-* 22:00:00";
      Persistent = true;
      Unit = "galley-snapshots.service";
    };
    Install.WantedBy = [ "timers.target" ];
  };
}
