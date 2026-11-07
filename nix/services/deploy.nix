# nix/services/deploy.nix
#
# Unattended deploys from origin/main, and the `af` command that operates them.
#
# af-rebuild.service runs nix/services/deploy/af-deploy.py as root: it builds
# the exact commit at origin/main from its own clone in /var/lib/af-rebuild,
# switches, runs the critical checks and rolls back if they fail. A timer runs
# it every couple of minutes; `af deploy` runs it now. The script's docstring
# has the rules for what counts as a failure.
#
# The only root anyone gets from this is `systemctl start` of these fixed
# units. A NOPASSWD rule for nixos-rebuild would let the caller pick the flake,
# which is root for anything running as the user. Here the caller can only ask
# for origin/main to be deployed, and only a push to GitHub changes what that
# is.
#
# The deploy units are restartIfChanged = false: a deploy switches the system
# that defines these units, and must not be stopped by its own switch.
{ pkgs, lib, locals, ... }:

let
  # Where this box deploys from. A fork sets deployRepo in locals.json.
  repoUrl = locals.deployRepo or "https://github.com/t-eckert/ardent-forge.git";
  ownerRepo = lib.removeSuffix ".git" (lib.removePrefix "https://github.com/" repoUrl);
  # The development checkout, in the ~/Repos/github.com layout workspace-init uses.
  devCheckout = "/home/${locals.username}/Repos/github.com/${ownerRepo}";
  host = "ardent-forge";
  # Deploy reports have their own topic: alert-triage polls the alerts topic
  # and would start a triage run for every deploy message there.
  ntfyTopic = "http://127.0.0.1:8090/ardent-forge-deploys";

  deployUnit = { description, args ? "", extraEnv ? { } }: {
    inherit description;
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];
    restartIfChanged = false;
    path = with pkgs; [ git nix curl coreutils systemd tailscale ];
    environment = {
      AF_REPO_URL = repoUrl;
      AF_HOST = host;
      AF_NTFY = ntfyTopic;
    } // extraEnv;
    serviceConfig = {
      Type = "oneshot";
      ExecStart = "${pkgs.python3}/bin/python3 ${./deploy/af-deploy.py}${args}";
      StateDirectory = "af-rebuild";
      StateDirectoryMode = "0755";
      # A nixpkgs bump that was not built before pushing can take hours on the N150.
      TimeoutStartSec = "3h";
    };
  };

  af = pkgs.writeShellApplication {
    name = "af";
    runtimeInputs = with pkgs; [ git jq coreutils gnugrep gnused nix python3 ];
    text = lib.replaceStrings
      [ "@repoUrl@" "@devCheckout@" "@host@" ]
      [ repoUrl devCheckout host ]
      (builtins.readFile ./deploy/af.sh);
  };
in
{
  systemd.services.af-rebuild = deployUnit {
    description = "Deploy origin/main";
  };
  systemd.services.af-rebuild-retry = deployUnit {
    description = "Deploy origin/main, retrying a commit that failed";
    args = " --retry";
  };
  # The rollback drill: deploy origin/main with the critical check forced to
  # fail, so the box switches back. Needs a password on purpose.
  systemd.services.af-rebuild-drill = deployUnit {
    description = "Deploy origin/main and force a rollback (drill)";
    args = " --force";
    extraEnv.AF_DRILL = "1";
  };

  systemd.timers.af-rebuild = {
    description = "Check origin/main for a new commit to deploy";
    wantedBy = [ "timers.target" ];
    timerConfig = {
      OnBootSec = "3min";
      OnUnitInactiveSec = "2min";
      Unit = "af-rebuild.service";
    };
  };

  # sudo matches the command as resolved from PATH without following
  # symlinks, so these name the /run/current-system path (see crucible.nix).
  security.sudo.extraRules = [{
    users = [ locals.username ];
    commands = map (unit: {
      command = "/run/current-system/sw/bin/systemctl start ${unit}";
      options = [ "NOPASSWD" ];
    }) [ "af-rebuild" "af-rebuild-retry" ];
  }];

  environment.systemPackages = [ af ];
}
