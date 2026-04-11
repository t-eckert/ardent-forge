# nix/home.nix
{ config, pkgs, lib, dotfiles, ... }:

{
  imports = [
    # Import the Linux home config from dotfiles
    # This brings in: zsh, git, neovim, starship, and core packages
    "${dotfiles}/nix/linux/default.nix"
  ];

  home = {
    username = "thomaseckert";
    homeDirectory = "/home/thomaseckert";
    stateVersion = "24.05";
  };

  # Ardent Forge-specific additions on top of dotfiles
  home.packages = with pkgs; [
    # Python tooling for Ardent Forge development
    uv
    python313

    # Container management
    podman

    # Claude Code CLI (installed via npm)
    # Run: npm install -g @anthropic-ai/claude-code
    # after first login

    # Monitoring tools
    prometheus
    grafana-loki
  ];

  # Environment variables for dev work
  home.sessionVariables = {
    FORGE_DB_PATH = "/data/ardent-forge/forge.db";
    FORGE_WORKSPACE_DIR = "/data/ardent-forge/repos";
  };

  # Git config — clone the ardent-forge repo on first setup
  home.file.".local/bin/forge-setup" = {
    executable = true;
    text = ''
      #!/usr/bin/env bash
      set -euo pipefail

      REPO_DIR="/data/ardent-forge/repo"
      if [ ! -d "$REPO_DIR/.git" ]; then
        echo "Cloning ardent-forge repo..."
        git clone https://github.com/t-eckert/ardent-forge.git "$REPO_DIR"
        cd "$REPO_DIR"
        uv sync
        echo "Done. Repo at $REPO_DIR, venv ready."
      else
        echo "Repo already exists at $REPO_DIR"
      fi

      # Create 1Password env files from examples
      for f in /etc/ardent-forge/*.env.example; do
        target="/data/ardent-forge/$(basename "$f" .example)"
        if [ ! -f "$target" ]; then
          cp "$f" "$target"
          echo "Created $target from example — edit op:// URIs if needed"
        fi
      done

      echo "Setup complete. Run: sudo systemctl start ardent-forge"
    '';
  };
}
