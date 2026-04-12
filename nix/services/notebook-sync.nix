# nix/services/notebook-sync.nix
#
# Runs syncshot against the local Notebook clone, committing and pushing
# every 30 seconds. The clone is created on first start if missing.
# Everything runs inside `op run` so FORGE_GITHUB_TOKEN is available for
# both the initial clone and syncshot's push.
{ config, pkgs, lib, locals, ... }:

let
  notebookDir = "/data/ardent-forge/notebook";
  repoDir = "/data/ardent-forge/repo";

  startScript = pkgs.writeShellScript "notebook-sync-start" ''
    set -euo pipefail
    export PATH=${lib.makeBinPath (with pkgs; [ git coreutils python313 _1password-cli ])}:$PATH

    exec op run --env-file ${repoDir}/nix/services/notebook-sync.env -- ${pkgs.bash}/bin/bash -c '
      set -euo pipefail

      if [ ! -d "${notebookDir}/.git" ]; then
        echo "Cloning Notebook into ${notebookDir}"
        git -c credential.helper= clone \
          "https://x-access-token:$FORGE_GITHUB_TOKEN@github.com/t-eckert/Notebook.git" \
          "${notebookDir}"
      fi

      cd "${notebookDir}"
      git remote set-url origin https://github.com/t-eckert/Notebook.git
      git config user.name "Ardent Forge"
      git config user.email "forge@${locals.tailnetDomain}"
      git config credential.helper "!f() { echo username=x-access-token; echo \"password=$FORGE_GITHUB_TOKEN\"; }; f"

      exec python3 ${repoDir}/scripts/syncshot.py --period 30
    '
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

      EnvironmentFile = "/etc/ardent-forge/op-token";

      ExecStart = "${startScript}";

      Restart = "on-failure";
      RestartSec = 30;
    };
  };

  systemd.tmpfiles.rules = [
    "d ${notebookDir} 0750 ${locals.username} users -"
  ];

  # Env template — secrets resolved by `op run`
  environment.etc."ardent-forge/notebook-sync.env.example".text = ''
    FORGE_GITHUB_TOKEN=op://Ardent Forge/github-pat/credential
  '';
}
