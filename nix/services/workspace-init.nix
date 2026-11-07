# nix/services/workspace-init.nix
#
# Clones any repos listed in /etc/ardent-forge/workspace-repos that are
# missing from ~/Repos/github.com/owner/repo. Runs once at boot as a oneshot;
# re-run with `sudo systemctl start workspace-init` after adding a repo.
#
# The list is read when the service runs, not at build time: it is the user's
# own file (one owner/repo per line, # comments allowed), the service runs as
# the user and only clones, so the build never needs to see it and adding a
# repo needs no rebuild. See nix/workspace-repos.example.
#
# GH_TOKEN is resolved by `op run` from workspace-init.env at start time, so
# no secret ever lands in the Nix store. The op service-account token itself
# comes from /etc/ardent-forge/op-token, which is placed by hand on the box.
{ pkgs, lib, locals, ... }:

let
  workspaceDir = "/home/${locals.username}/Repos/github.com";
  envFile = ./workspace-init.env;
  reposFile = "/etc/ardent-forge/workspace-repos";

  cloneScript = pkgs.writeShellScript "workspace-init" ''
    set -euo pipefail
    export PATH=${lib.makeBinPath (with pkgs; [ git coreutils gnused ])}:$PATH

    clone_if_missing() {
      local slug="$1"
      local dest="${workspaceDir}/$slug"

      if [ -d "$dest/.git" ]; then
        echo "  ok  $slug"
        return
      fi

      echo "  clone $slug"
      mkdir -p "$(dirname "$dest")"
      git clone "https://x-access-token:''${GH_TOKEN}@github.com/$slug.git" "$dest"
    }

    if [ ! -f ${reposFile} ]; then
      echo "workspace-init: no ${reposFile}, nothing to clone"
      exit 0
    fi

    # Blank lines and # comments are skipped; anything that isn't owner/repo
    # is reported and skipped rather than handed to git.
    mapfile -t repos < <(sed -e 's/#.*//' -e 's/[[:space:]]//g' -e '/^$/d' ${reposFile})
    echo "workspace-init: checking ''${#repos[@]} repos"
    for slug in "''${repos[@]}"; do
      if [[ "$slug" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
        clone_if_missing "$slug"
      else
        echo "  skip $slug (not owner/repo)"
      fi
    done
    echo "workspace-init: done"
  '';
in {
  systemd.services.workspace-init = {
    description = "Clone declared workspace repos into ~/Repos/github.com";
    wantedBy = [ "multi-user.target" ];
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];

    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      User = locals.username;
      Group = "users";

      # Provides OP_SERVICE_ACCOUNT_TOKEN so `op run` can resolve op:// refs.
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
