# nix/services/ardent-forge.nix
{ config, pkgs, lib, locals, ... }:

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
      HOME = "/home/${locals.username}";
    };

    serviceConfig = {
      Type = "simple";
      User = locals.username;
      Group = "users";
      WorkingDirectory = repoDir;

      # Load 1Password service account token
      EnvironmentFile = "/etc/ardent-forge/op-token";

      # 1Password injects secrets as env vars
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
        "/home/${locals.username}"
      ];
      PrivateTmp = true;
    };
  };

  # The 1Password env file maps op:// URIs to env var names.
  # This file contains NO secrets — only references.
  environment.etc."ardent-forge/forge.env.example".text = ''
    FORGE_ANTHROPIC_API_KEY=op://Ardent Forge/anthropic-api-key/credential
    FORGE_GITHUB_TOKEN=op://Ardent Forge/github-pat/credential
    FORGE_LINEAR_API_KEY=op://Ardent Forge/linear-api-key/credential
    FORGE_LINEAR_TEAM_ID=op://Ardent Forge/linear-team-id/credential
  '';
}
