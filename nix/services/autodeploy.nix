# nix/services/autodeploy.nix
#
# Polls origin/main every 5 minutes. If there are new commits, pulls and runs
# `nixos-rebuild switch`. On failure, posts to the local NTFY instance.
#
# NixOS keeps the previous generation on activation failure, so a broken
# commit degrades to "running stale code + NTFY alert" rather than a brick.
{ config, pkgs, lib, locals, ... }:

let
  repoDir = "/data/ardent-forge/repo";
  ntfyTopic = "ardent-forge-deploy";

  autodeployScript = pkgs.writeShellScript "ardent-forge-autodeploy" ''
    set -uo pipefail
    export PATH=${lib.makeBinPath (with pkgs; [
      git nixos-rebuild systemd coreutils curl gnused
    ])}:$PATH

    cd ${repoDir}
    git config --global --add safe.directory ${repoDir}

    git fetch --quiet origin main || {
      echo "git fetch failed"
      exit 0  # transient — try again next tick
    }

    local_sha=$(git rev-parse HEAD)
    remote_sha=$(git rev-parse origin/main)

    if [ "$local_sha" = "$remote_sha" ]; then
      exit 0
    fi

    echo "New commits: $local_sha -> $remote_sha"

    notify() {
      local title="$1"
      local body="$2"
      local priority="$3"
      curl -fsS \
        -H "Title: $title" \
        -H "Priority: $priority" \
        -H "Tags: ardent-forge" \
        -d "$body" \
        http://127.0.0.1:8090/${ntfyTopic} || true
    }

    short_remote=$(echo "$remote_sha" | cut -c1-8)
    commit_msg=$(git log -1 --format=%s "$remote_sha" || echo "")

    if ! git pull --ff-only --quiet origin main; then
      notify "Ardent Forge deploy: git pull failed" \
             "Could not fast-forward to $short_remote" "high"
      exit 1
    fi

    log=$(mktemp)
    if nixos-rebuild switch --flake ${repoDir}/nix#ardent-forge --impure >"$log" 2>&1; then
      systemctl restart ardent-forge || true
      notify "Ardent Forge deployed $short_remote" "$commit_msg" "default"
      rm -f "$log"
      exit 0
    else
      tail=$(tail -c 2000 "$log")
      notify "Ardent Forge deploy FAILED at $short_remote" \
             "$commit_msg

--- nixos-rebuild tail ---
$tail" "high"
      rm -f "$log"
      exit 1
    fi
  '';
in {
  systemd.services.ardent-forge-autodeploy = {
    description = "Pull main and nixos-rebuild switch if there are new commits";
    # Run as root — nixos-rebuild switch needs it.
    serviceConfig = {
      Type = "oneshot";
      ExecStart = "${autodeployScript}";
    };
    # Don't run before the network/ntfy are up.
    after = [ "network-online.target" "podman-ntfy.service" ];
    wants = [ "network-online.target" ];
  };

  systemd.timers.ardent-forge-autodeploy = {
    description = "Poll origin/main for new commits";
    wantedBy = [ "timers.target" ];
    timerConfig = {
      OnBootSec = "2min";
      OnUnitInactiveSec = "5min";
      Unit = "ardent-forge-autodeploy.service";
    };
  };
}
