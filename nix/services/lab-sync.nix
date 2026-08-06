# nix/services/lab-sync.nix
#
# Runs syncshot against ~/Repos/lab — the directory marimo edits notebooks in —
# committing and pushing every 60 seconds. Same pattern as notebook-sync.nix,
# but the repo is created locally by marimo's ExecStartPre rather than cloned,
# so this bootstraps the remote and the first commit instead of cloning.
#
# Everything runs inside `op run` so FORGE_GITHUB_TOKEN is available for push.
{ pkgs, lib, locals, ... }:

let
  labDir = "/home/${locals.username}/Repos/lab";
  repoDir = "/data/ardent-forge/repo";
  remote = "github.com/t-eckert/lab.git";

  startScript = pkgs.writeShellScript "lab-sync-start" ''
    set -euo pipefail
    export PATH=${lib.makeBinPath (with pkgs; [ git coreutils python313 _1password-cli ])}:$PATH

    exec op run --env-file ${repoDir}/nix/services/lab-sync.env -- ${pkgs.bash}/bin/bash -c '
      set -euo pipefail

      cd "${labDir}"

      # marimo.service ExecStartPre already does this, but lab-sync has no
      # ordering guarantee against it and `git -C` on a non-repo is fatal.
      if [ ! -d .git ]; then
        git init
      fi

      git symbolic-ref HEAD refs/heads/main

      git config user.name "Ardent Forge"
      git config user.email "forge@${locals.tailnetDomain}"
      git config credential.helper "!f() { echo username=x-access-token; echo \"password=$FORGE_GITHUB_TOKEN\"; }; f"

      git remote add origin "https://${remote}" 2>/dev/null \
        || git remote set-url origin "https://${remote}"

      # syncshot reads ahead/behind from `git status -b`, which reports nothing
      # without an upstream. Seed a commit and set tracking on first run so the
      # very first sync has a branch to compare against.
      if ! git rev-parse HEAD >/dev/null 2>&1; then
        if [ ! -f .gitignore ]; then
          printf "%s\n" "__pycache__/" "__marimo__/" ".venv/" "*.pyc" > .gitignore
        fi
        git add -A
        git commit -m "Initialize lab" --allow-empty
      fi

      if ! git rev-parse --abbrev-ref main@{upstream} >/dev/null 2>&1; then
        git push -u origin main
      fi

      exec python3 ${repoDir}/scripts/syncshot.py --period 60
    '
  '';
in {
  systemd.services.ardent-forge-lab-sync = {
    description = "Ardent Forge — syncshot loop for the marimo lab notebooks";
    wantedBy = [ "multi-user.target" ];
    after = [ "network-online.target" "marimo.service" ];
    wants = [ "network-online.target" ];

    # Neutral HOME — the user's dotfiles gitconfig rewrites https://github.com/
    # to git@github.com:, and no SSH key is configured for this service, so the
    # rewrite would break every push. Same reason as notebook-sync.nix.
    environment = {
      HOME = "/data/ardent-forge";
    };

    serviceConfig = {
      Type = "simple";
      User = locals.username;
      Group = "users";
      WorkingDirectory = labDir;

      EnvironmentFile = "/etc/ardent-forge/op-token";

      ExecStart = "${startScript}";

      Restart = "on-failure";
      RestartSec = 30;
    };
  };

  # Env template — secrets resolved by `op run`
  environment.etc."ardent-forge/lab-sync.env.example".text = ''
    FORGE_GITHUB_TOKEN=op://Ardent Forge/github-pat/credential
  '';
}
