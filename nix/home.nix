# nix/home.nix
#
# Standalone home config for the Bee Link. The dotfiles linux config has
# nixpkgs compatibility issues (nodePackages removed), so we define the
# essentials here directly. Revisit dotfiles import once dotfiles repo
# is updated for latest nixpkgs-unstable.
{ config, pkgs, lib, locals, ... }:

{
  home = {
    username = locals.username;
    homeDirectory = "/home/${locals.username}";
    stateVersion = "24.05";
  };

  programs.home-manager.enable = true;

  # Shell
  programs.zsh = {
    enable = true;
    enableCompletion = true;
    autosuggestion.enable = true;
    syntaxHighlighting.enable = true;
  };

  programs.starship.enable = true;

  programs.git = {
    enable = true;
    userName = "Thomas Eckert";
    userEmail = "thomas.eckert@hey.com";
  };

  programs.neovim = {
    enable = true;
    defaultEditor = true;
  };

  home.packages = with pkgs; [
    # Core tools
    git
    gh
    ripgrep
    fzf
    bat
    jq
    yq
    tree
    curl
    wget
    lazygit
    htop

    # Languages
    go
    gopls
    nodejs_22
    python313
    uv
    deno

    # Containers
    podman

    # Terminal
    zellij
    atuin
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
