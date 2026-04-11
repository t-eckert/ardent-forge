# nix/services/ardent-forge.nix
{ config, pkgs, lib, ... }:

let
  forgeDir = "/data/ardent-forge";
  repoDir = "${forgeDir}/repo";
in {
  systemd.services.ardent-forge = {
    description = "Ardent Forge — agentic development platform";
    wantedBy = [ "multi-user.target" ];
    after = [ "network-online.target" "postgresql.service" "tailscaled.service" ];
    wants = [ "network-online.target" ];
    requires = [ "postgresql.service" ];

    path = with pkgs; [
      git
      gh
      _1password-cli
      nodejs_22  # for Claude Code CLI
      uv
    ];

    environment = {
      FORGE_DB_PATH = "${forgeDir}/forge.db";
      FORGE_WORKSPACE_DIR = "${forgeDir}/repos";
      FORGE_HOST = "127.0.0.1";
      FORGE_PORT = "7030";
      HOME = "/home/thomaseckert";
    };

    serviceConfig = {
      Type = "simple";
      User = "thomaseckert";
      Group = "users";
      WorkingDirectory = repoDir;

      # 1Password injects secrets as env vars
      # Requires: `op signin` done once interactively as thomaseckert
      ExecStart = pkgs.writeShellScript "ardent-forge-start" ''
        exec ${pkgs._1password-cli}/bin/op run \
          --env-file ${forgeDir}/forge.env \
          -- ${pkgs.uv}/bin/uv run forge
      '';

      Restart = "on-failure";
      RestartSec = 10;

      # Hardening
      NoNewPrivileges = true;
      ProtectSystem = "strict";
      ProtectHome = "read-only";
      ReadWritePaths = [
        forgeDir
        "/home/thomaseckert"
      ];
      PrivateTmp = true;
    };
  };

  # The 1Password env file maps op:// URIs to env var names.
  # This file contains NO secrets — only references.
  environment.etc."ardent-forge/forge.env.example".text = ''
    FORGE_ANTHROPIC_API_KEY=op://ArdentForge/anthropic-api-key/credential
    FORGE_GITHUB_TOKEN=op://ArdentForge/github-pat/credential
    FORGE_LINEAR_API_KEY=op://ArdentForge/linear-api-key/credential
    FORGE_LINEAR_TEAM_ID=op://ArdentForge/linear-team-id/credential
  '';
}
