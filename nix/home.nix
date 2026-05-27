# nix/home.nix
#
# Pulls in the full dotfiles dev environment and adds forge-specific extras.
{ config, pkgs, lib, dotfiles, locals, ... }:

{
  imports = [
    # Full dotfiles home environment: packages, shell, git, ssh, neovim, starship
    "${dotfiles}/nix/home"
  ];

  home = {
    username = locals.username;
    homeDirectory = "/home/${locals.username}";
    # stateVersion comes from dotfiles home module ("24.05")
  };

  # dotfiles uses mkOutOfStoreSymlink pointing to ~/Repos/... which doesn't exist
  # here — override to use the store path from the dotfiles flake input instead.
  xdg.configFile."nvim" = lib.mkForce {
    source = "${dotfiles}/config/nvim";
    recursive = true;
  };

  # Forge-specific packages not covered by dotfiles
  home.packages = with pkgs; [
    uv              # Python package manager
    openssl
    pkg-config
    podman-compose
    unzip
  ];

  # Forge-specific environment variables
  home.sessionVariables = {
    FORGE_DB_PATH = "/data/ardent-forge/forge.db";
    FORGE_WORKSPACE_DIR = "/home/${locals.username}/Repos";
  };

  # Rebuild script — updates flake inputs then switches the system
  home.file.".local/bin/af-rebuild" = {
    executable = true;
    text = ''
      #!/usr/bin/env bash
      set -euo pipefail

      FLAKE_DIR="/data/ardent-forge/repo/nix"

      echo "Updating flake inputs..."
      nix flake update --flake "$FLAKE_DIR"

      echo "Rebuilding system..."
      if sudo nixos-rebuild switch --flake "$FLAKE_DIR#ardent-forge" --impure; then
        echo "Switch complete."
      else
        echo "Live switch failed (likely critical system changes). Staging for next boot..."
        sudo nixos-rebuild boot --flake "$FLAKE_DIR#ardent-forge" --impure
        echo "Done. Reboot when ready: sudo reboot"
      fi
    '';
  };

  # First-boot setup script
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
