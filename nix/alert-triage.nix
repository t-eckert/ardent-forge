# nix/alert-triage.nix
#
# Unattended triage of the Grafana alerts that reach ntfy. A timer polls the
# topic; anything new and actionable is handed to `claude -p`, which diagnoses
# it and -- where the playbook allows -- fixes it or opens a PR.
#
# This is a home-manager (user) unit rather than a system one for two reasons:
# `claude` authenticates from ~/.claude/.credentials.json, and `gh` from the
# user's own config. Lingering is enabled for this user, so it still runs
# without anyone logged in.
#
# The limits are enforced in alert-triage.py, not in the prompt, so a triage run
# that reasons badly is still bounded: signature cooldown, daily run and PR
# caps, and a PAUSED file that stops everything. The tool allowlist is passed on
# the command line; anything outside it fails closed and the run degrades to
# diagnosis. Note what is absent from it -- no sudo and no `nixos-rebuild
# switch`, which this user could not run unattended anyway since it needs a
# password. That is the backstop: the worst outcome is a bad PR, not a bad box.
{ config, pkgs, lib, ... }:

let
  repo = "/data/ardent-forge/repo";
  script = "${repo}/nix/services/alert-triage.py";
  stateDir = "${config.home.homeDirectory}/.local/state/alert-triage";
in
{
  systemd.user.services.alert-triage = {
    Unit = {
      Description = "Triage Grafana alerts that reached ntfy";
      # Nothing to poll if the notification path itself is down.
      After = [ "network-online.target" ];
    };
    Service = {
      Type = "oneshot";
      # PATH has to carry claude, gh and git explicitly: a user unit does not
      # source the login shell, so ~/.local/bin is not on it by default.
      Environment = [
        "PATH=${config.home.homeDirectory}/.local/bin:/run/current-system/sw/bin:/etc/profiles/per-user/${config.home.username}/bin"
        "AT_STATE_DIR=${stateDir}"
        "AT_PLAYBOOK=${repo}/nix/services/alert-triage-playbook.md"
        "AT_NTFY=http://127.0.0.1:8090/ardent-forge"
        # One PR a day. A bad night is then one thing to unwind, not several.
        "AT_MAX_PRS=1"
        "AT_MAX_RUNS=8"
        "AT_COOLDOWN_H=24"
      ];
      ExecStart = "${pkgs.python3}/bin/python3 ${script}";
      # A single triage run reads logs, may build, and may open a PR. Well
      # under this in practice; the cap exists so a wedged run cannot occupy
      # the timer indefinitely.
      TimeoutStartSec = "20min";
      WorkingDirectory = repo;
    };
  };

  systemd.user.timers.alert-triage = {
    Unit.Description = "Poll for Grafana alerts to triage";
    Timer = {
      # Ten minutes is well inside ntfy's 12h retention, so nothing is missed
      # between runs, and slow enough that a flapping alert does not spend the
      # daily budget in an hour.
      OnBootSec = "5min";
      OnUnitActiveSec = "10min";
      Unit = "alert-triage.service";
    };
    Install.WantedBy = [ "timers.target" ];
  };

  home.activation.alertTriageState =
    lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      $DRY_RUN_CMD mkdir -p ${stateDir}/verdicts
    '';
}
