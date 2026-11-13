# nix/services/notebook-sync.nix
#
# Runs syncshot against the local Notebook clone, committing and pushing
# every 30 seconds. The clone is created on first start if missing.
# git gets the GitHub token from 1Password whenever it needs one, through
# github-pat-credential.nix, so rotating the token needs no restart.
{ config, pkgs, lib, locals, ... }:

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

    exec python3 ${../../scripts/syncshot.py} --period 30
  '';
in {
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
