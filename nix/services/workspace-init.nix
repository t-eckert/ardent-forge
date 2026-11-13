# nix/services/workspace-init.nix
#
# Clones any repos listed in the `workspace-repos` 1Password item that are
# missing from ~/Repos/github.com/owner/repo. Runs once at boot as a oneshot;
# `af repos sync` (or `af repos add`) runs it again.
#
# The list lives in 1Password, not in this repo or on this disk: the repo is
# public, and a list of private repo names should not end up here by accident,
# while a file on the box would not survive the box. Edit it with
# `af repos add|remove` or in the 1Password app. The item is a Secure Note in
# the "Ardent Forge" vault, one owner/repo per line, # comments allowed.
#
# Each run copies the list to /var/lib/workspace-init/repos so `af repos list`
# can show it without a 1Password sign-in.
#
# GH_TOKEN is resolved by `op run` from workspace-init.env at start time and is
# handed to git through a credential helper given with `git -c`, which is not
# written into the clone. Never put the token in the clone URL: git saves the
# URL, token included, in the clone's .git/config.
{ pkgs, lib, locals, ... }:

let
  workspaceDir = "/home/${locals.username}/Repos/github.com";
  envFile = ./workspace-init.env;
  stateDir = "/var/lib/workspace-init";
  reposRef = "op://Ardent Forge/workspace-repos/notesPlain";

  cloneScript = pkgs.writeShellScript "workspace-init" ''
    set -euo pipefail
    export PATH=${lib.makeBinPath (with pkgs; [ git coreutils gnused _1password-cli ])}:$PATH

    # The helper reads $GH_TOKEN when git runs it, so only this process ever
    # holds the value. The empty helper first clears any configured ones.
    helper='!f() { echo username=x-access-token; echo "password=$GH_TOKEN"; }; f'

    clone_if_missing() {
      local slug="$1"
      local dest="${workspaceDir}/$slug"

      if [ -d "$dest/.git" ]; then
        echo "  ok  $slug"
        return
      fi

      echo "  clone $slug"
      mkdir -p "$(dirname "$dest")"
      git -c credential.helper= -c credential.helper="$helper" \
        clone --quiet "https://github.com/$slug.git" "$dest"
    }

    list=$(op read "${reposRef}")
    printf '%s\n' "$list" > ${stateDir}/repos

    # Blank lines and # comments are skipped; anything that isn't owner/repo
    # is reported and skipped rather than handed to git.
    mapfile -t repos < <(printf '%s\n' "$list" | sed -e 's/#.*//' -e 's/[[:space:]]//g' -e '/^$/d')
    echo "workspace-init: checking ''${#repos[@]} repos"
    failed=0
    for slug in "''${repos[@]}"; do
      if [[ "$slug" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
        clone_if_missing "$slug" || { echo "  FAILED $slug"; failed=1; }
      else
        echo "  skip $slug (not owner/repo)"
      fi
    done
    echo "workspace-init: done"
    exit "$failed"
  '';
in {
  systemd.services.workspace-init = {
    description = "Clone declared workspace repos into ~/Repos/github.com";
    wantedBy = [ "multi-user.target" ];
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];

    # Neutral HOME: the user's git config adds gh's credential helper for
    # github.com, which would clone with the user's own token instead of
    # GH_TOKEN. Same reason as notebook-sync.nix.
    environment.HOME = stateDir;

    serviceConfig = {
      Type = "oneshot";
      # No RemainAfterExit: with it the unit stays "active" after the boot
      # run, and every later `systemctl start` is a no-op that clones nothing.
      User = locals.username;
      Group = "users";
      StateDirectory = "workspace-init";
      StateDirectoryMode = "0755";

      # Provides OP_SERVICE_ACCOUNT_TOKEN so `op` can resolve op:// refs.
      EnvironmentFile = "/etc/ardent-forge/op-token";

      ExecStart = pkgs.writeShellScript "workspace-init-start" ''
        exec ${pkgs._1password-cli}/bin/op run \
          --env-file ${envFile} \
          -- ${cloneScript}
      '';

      NoNewPrivileges = true;
      ProtectSystem = "strict";
      ProtectHome = "read-only";
      ReadWritePaths = [ "/home/${locals.username}/Repos" ];
      PrivateTmp = true;
    };
  };

  security.sudo.extraRules = [{
    users = [ locals.username ];
    commands = [{
      command = "/run/current-system/sw/bin/systemctl start workspace-init";
      options = [ "NOPASSWD" ];
    }];
  }];
}
