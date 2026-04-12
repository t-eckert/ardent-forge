# nix/services/notebook-sync.nix
#
# Runs syncshot against the local Notebook clone, committing and pushing
# every 30 seconds. Initial clone is performed by ExecStartPre if the
# directory is empty.
{ config, pkgs, lib, locals, ... }:

let
  notebookDir = "/data/ardent-forge/notebook";
  notebookRepo = "https://github.com/t-eckert/Notebook.git";
  repoDir = "/data/ardent-forge/repo";

  preStart = pkgs.writeShellScript "notebook-sync-pre" ''
    set -euo pipefail
    export PATH=${lib.makeBinPath [ pkgs.git pkgs.coreutils ]}:$PATH

    if [ ! -d "${notebookDir}/.git" ]; then
      echo "Cloning Notebook into ${notebookDir}"
      git clone "${notebookRepo}" "${notebookDir}"
    fi

    cd "${notebookDir}"
    git config user.name "Ardent Forge"
    git config user.email "forge@${locals.tailnetDomain}"
    # Use FORGE_GITHUB_TOKEN for auth via the credential helper
    git config credential.helper '!f() { echo "username=x-access-token"; echo "password=$FORGE_GITHUB_TOKEN"; }; f'
  '';
in {
  systemd.services.ardent-forge-notebook-sync = {
    description = "Ardent Forge — syncshot loop for the Notebook vault";
    wantedBy = [ "multi-user.target" ];
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];

    path = with pkgs; [ git coreutils python313 ];

    environment = {
      HOME = "/home/${locals.username}";
    };

    serviceConfig = {
      Type = "simple";
      User = locals.username;
      Group = "users";
      WorkingDirectory = notebookDir;

      EnvironmentFile = "/etc/ardent-forge/op-token";

      ExecStartPre = "+${preStart}";
      ExecStart = pkgs.writeShellScript "notebook-sync-start" ''
        exec ${pkgs._1password-cli}/bin/op run \
          --env-file ${repoDir}/nix/services/notebook-sync.env \
          -- ${pkgs.python313}/bin/python3 ${repoDir}/scripts/syncshot.py --period 30
      '';

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
