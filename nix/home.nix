# nix/home.nix
#
# Imports dotfiles modules for shell, git, neovim, and starship config.
# Packages are managed here (not via dotfiles packages.nix) to avoid
# the dotfiles `self` dependency for custom Go tools.
{ config, pkgs, lib, dotfiles, locals, ... }:

{
  imports = [
    # Dotfiles modules — full shell/editor/git config
    "${dotfiles}/nix/home/shell.nix"
    "${dotfiles}/nix/home/git.nix"
    "${dotfiles}/nix/home/programs/neovim.nix"
    "${dotfiles}/nix/home/programs/starship.nix"
  ];

  home = {
    username = locals.username;
    homeDirectory = "/home/${locals.username}";
    stateVersion = "24.05";
  };

  programs.home-manager.enable = true;

  # XDG directories
  xdg = {
    enable = true;
    configHome = "${config.home.homeDirectory}/.config";
    dataHome = "${config.home.homeDirectory}/.local/share";
    cacheHome = "${config.home.homeDirectory}/.cache";
  };

  home.sessionVariables = {
    EDITOR = "nvim";
    VISUAL = "nvim";
    BAT_THEME = "base16";
    FORGE_DB_PATH = "/data/ardent-forge/forge.db";
    FORGE_WORKSPACE_DIR = "/data/ardent-forge/repos";
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
    htop

    # Languages
    go
    gopls
    nodejs_22
    python313
    uv
    deno
    rustup

    # Language servers (for Neovim)
    lua-language-server
    typescript-language-server
    nil
    pyright
    stylua
    nixpkgs-fmt
    prettier
    shellcheck
    fd
    tree-sitter

    # Cloud & Infra
    kubectl
    kubernetes-helm
    k9s
    flyctl
    terraform

    # Containers
    podman

    # Terminal
    zellij
    atuin
    lazygit

    # Networking
    caddy
    nmap
  ];

  # Link Neovim config from dotfiles
  xdg.configFile."nvim" = {
    source = "${dotfiles}/config/nvim";
    recursive = true;
  };

  # Link Zellij config from dotfiles
  xdg.configFile."zellij" = {
    source = "${dotfiles}/config/zellij";
    recursive = true;
  };

  # Link Atuin config from dotfiles
  xdg.configFile."atuin" = {
    source = "${dotfiles}/config/atuin";
    recursive = true;
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
