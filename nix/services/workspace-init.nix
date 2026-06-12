# nix/services/workspace-init.nix
#
# Clones any repos declared in locals.workspaceRepos that are missing from
# ~/Repos/github.com/owner/repo. Runs once at boot as a oneshot; re-run
# manually with `systemctl start workspace-init` after adding a new repo.
#
# Credentials come from the same op-token + forge.env path as ardent-forge,
# so GH_TOKEN is resolved by `op run` at start time — no secrets in the Nix
# store.
{ pkgs, lib, locals, ... }:

let
  workspaceDir = "/home/${locals.username}/Repos/github.com";
  repos = locals.workspaceRepos or [];

  cloneScript = pkgs.writeShellScript "workspace-init" ''
    set -euo pipefail
    export PATH=${lib.makeBinPath (with pkgs; [ git coreutils ])}:$PATH

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

    echo "workspace-init: checking ${toString (builtins.length repos)} repos"
    ${lib.concatMapStrings (repo: "clone_if_missing ${lib.escapeShellArg repo}\n") repos}
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
          --env-file /data/ardent-forge/forge.env \
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
