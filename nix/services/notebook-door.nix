# nix/services/notebook-door.nix
#
# The Notebook's MCP door, at nb.<tailnet>/mcp: the one careful way other agents
# read and write the Notebook. stet is its first caller. Each caller has a token
# and a grant of the folders and notes it may read and write; a deny list wins
# over every grant. Each write holds a syncshot pause lease, refuses if GitHub
# is ahead on that note, and is committed by syncshot with the caller as the
# git author. The door never pulls, pushes or commits by itself.
#
# The grants name notes, and this repo is public, so they live in
# /etc/ardent-forge/notebook-door.json, placed by hand like locals.json.
# notebook-door/config.example.json is its template. Tokens come from
# 1Password through notebook-door.env. See notebook-door/README.md.
{ config, pkgs, lib, locals, syncshot, ... }:

let
  notebookDir = "/data/ardent-forge/notebook";
  door = ../../notebook-door;
in {
  systemd.services.notebook-door = {
    description = "The Notebook's MCP door";
    wantedBy = [ "multi-user.target" ];
    after = [ "network-online.target" "ardent-forge-notebook-sync.service" ];
    wants = [ "network-online.target" ];
    # The door's config is placed by hand; until it is, there is nothing to serve.
    unitConfig.ConditionPathExists = "/etc/ardent-forge/notebook-door.json";

    path = with pkgs; [ git python313 coreutils ];
    environment = {
      # The same neutral HOME as notebook-sync, so git uses the clone's own
      # credential helpers and not the user's dotfiles.
      HOME = "/data/ardent-forge";
      SYNCSHOT = "${syncshot}/syncshot.py";
      SYNCSHOT_OWNER = "notebook-door";
      NOTEBOOK_DOOR_CONFIG = "/etc/ardent-forge/notebook-door.json";
      NOTEBOOK_DOOR_PORT = "8095";
      # Writes land here first, on the Notebook's filesystem but outside its
      # tree, and are renamed in, so syncshot never commits half a note.
      NOTEBOOK_DOOR_SCRATCH = "/data/ardent-forge/notebook-door";
    };

    serviceConfig = {
      Type = "simple";
      User = locals.username;
      Group = "users";
      WorkingDirectory = notebookDir;
      # OP_SERVICE_ACCOUNT_TOKEN, for `op run` and for git's credential helper.
      EnvironmentFile = "/etc/ardent-forge/op-token";
      ExecStart = pkgs.writeShellScript "notebook-door-start" ''
        exec ${pkgs._1password-cli}/bin/op run --env-file ${./notebook-door.env} \
          -- ${pkgs.nodejs_24}/bin/node ${door}/src/main.ts
      '';
      Restart = "on-failure";
      RestartSec = 10;
      NoNewPrivileges = true;
      PrivateTmp = true;
    };
  };

  systemd.tmpfiles.rules = [
    "d /data/ardent-forge/notebook-door 0700 ${locals.username} users -"
  ];
}
