# nix/services/notebook-sync.nix
#
# Runs syncshot against the local Notebook clone, committing and pushing
# every 30 seconds. The clone is created on first start if missing. syncshot is
# the flake input of that name, the same source the Mac runs: on a conflict it
# stops syncing and waits to be resolved by hand, rather than committing the
# markers. notebook-sync-check says so through ntfy, since nobody watches the log.
# git gets the GitHub token from 1Password whenever it needs one, through
# github-pat-credential.nix, so rotating the token needs no restart.
{ config, pkgs, lib, locals, syncshot, ... }:

let
  notebookDir = "/data/ardent-forge/notebook";
  runtimeDir = "/run/ardent-forge-notebook-sync";
  credential = import ./github-pat-credential.nix { inherit pkgs; };

  startScript = pkgs.writeShellScript "notebook-sync-start" ''
    set -euo pipefail
    export PATH=${lib.makeBinPath (with pkgs; [ git coreutils python313 ])}:$PATH

    if [ ! -d "${notebookDir}/.git" ]; then
      echo "Cloning Notebook into ${notebookDir}"
      git -c credential.helper= -c credential.helper=${credential} \
        clone https://github.com/t-eckert/Notebook.git "${notebookDir}"
    fi

    cd "${notebookDir}"
    git remote set-url origin https://github.com/t-eckert/Notebook.git
    git config user.name "Ardent Forge"
    git config user.email "forge@${locals.tailnetDomain}"
    git config --unset-all credential.helper || true
    git config credential.helper ""
    git config --add credential.helper "cache --timeout=3600 --socket=${runtimeDir}/git-credential"
    git config --add credential.helper ${credential}

    exec python3 ${syncshot}/syncshot.py run --period 30
  '';
  # syncshot refuses to sync while a rebase, merge, cherry-pick or revert is in
  # progress, and logs it once. That is safe, but the Forge's Notebook then goes
  # stale until someone resolves it, so this says so: once when the Notebook has
  # been stuck for five minutes or the sync loop is down, and once when it clears.
  checkScript = pkgs.writeShellScript "notebook-sync-check" ''
    set -u
    export PATH=${lib.makeBinPath (with pkgs; [ coreutils findutils curl systemd ])}
    gitDir="${notebookDir}/.git"
    alerted="$STATE_DIRECTORY/alerted"

    problem=""
    for marker in rebase-merge rebase-apply MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD; do
      if [ -e "$gitDir/$marker" ] && [ -n "$(find "$gitDir/$marker" -maxdepth 0 -mmin +5)" ]; then
        problem="a git operation ($marker) has been in progress for over five minutes, so syncshot has stopped syncing. Resolve it by hand in ${notebookDir}."
      fi
    done
    if ! systemctl is-active --quiet ardent-forge-notebook-sync.service; then
      problem="ardent-forge-notebook-sync is not running, so the Notebook is not syncing."
    fi

    send() {
      curl -s --max-time 10 -H "Title: $1" -H "Tags: $2" -d "$3" http://127.0.0.1:8090/ardent-forge || true
    }
    if [ -n "$problem" ] && [ ! -e "$alerted" ]; then
      send "Notebook sync stuck on ardent-forge" "warning,notebook" "$problem" && touch "$alerted"
    elif [ -z "$problem" ] && [ -e "$alerted" ]; then
      send "Notebook syncing again on ardent-forge" "white_check_mark,notebook" "The Forge's Notebook is syncing again." && rm -f "$alerted"
    fi
  '';
in {
  systemd.services.notebook-sync-check = {
    description = "Alert when the Forge's Notebook stops syncing";
    serviceConfig = {
      Type = "oneshot";
      User = locals.username;
      Group = "users";
      StateDirectory = "notebook-sync-check";
      ExecStart = "${checkScript}";
    };
  };
  systemd.timers.notebook-sync-check = {
    wantedBy = [ "timers.target" ];
    timerConfig = {
      OnBootSec = "5min";
      OnUnitActiveSec = "5min";
    };
  };

  systemd.services.ardent-forge-notebook-sync = {
    description = "Ardent Forge — syncshot loop for the Notebook vault";
    wantedBy = [ "multi-user.target" ];
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];

    # Neutral HOME — avoids picking up the user's dotfiles git config,
    # which rewrites https://github.com/ to git@github.com: (no SSH key
    # is configured for this service, so the rewrite breaks clone/push).
    environment = {
      HOME = "/data/ardent-forge";
    };

    serviceConfig = {
      Type = "simple";
      User = locals.username;
      Group = "users";
      WorkingDirectory = notebookDir;

      # OP_SERVICE_ACCOUNT_TOKEN, for the credential helper's `op read`.
      EnvironmentFile = "/etc/ardent-forge/op-token";
      # Holds the credential cache's socket; git refuses a looser directory.
      RuntimeDirectory = "ardent-forge-notebook-sync";
      RuntimeDirectoryMode = "0700";

      ExecStart = "${startScript}";

      Restart = "on-failure";
      RestartSec = 30;
    };
  };

  systemd.tmpfiles.rules = [
    "d ${notebookDir} 0750 ${locals.username} users -"
  ];
}
