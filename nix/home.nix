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
    openssl.dev
    pkg-config
    podman-compose
    unzip
    lsof
    pyright         # pyright-langserver for Claude Code pyright-lsp plugin

    # The dotfiles home module ships `rustup`, whose profile shim
    # `bin/rust-analyzer` is just the rustup proxy. The stable toolchain has no
    # rust-analyzer component installed, so the proxy "falls back" to itself on
    # PATH and recurses until it exits 1 ("error: infinite recursion detected").
    # That exit-1 is what crashes Claude Code's rust-analyzer-lsp plugin.
    # Ship the real nixpkgs binary and hiPrio it so it wins the bin/rust-analyzer
    # collision against the rustup shim.
    (lib.hiPrio rust-analyzer)
  ];

  # Forge-specific environment variables
  home.sessionVariables = {
    FORGE_DB_PATH = "/data/ardent-forge/forge.db";
    FORGE_WORKSPACE_DIR = "/home/${locals.username}/Repos";
    # openssl-sys (pulled in by async-stripe and others) requires both the dev
    # headers and the runtime libs. NixOS splits these across two outputs so
    # cargo can't find them via standard paths — set them explicitly.
    OPENSSL_DIR = "${pkgs.openssl.dev}";
    OPENSSL_LIB_DIR = "${pkgs.openssl.out}/lib";
    PKG_CONFIG_PATH = "${pkgs.openssl.dev}/lib/pkgconfig";
    # Prisma (chillest-subs) can't fetch a NixOS-specific query engine — its
    # CDN 404s on linux-nixos, so `prisma generate` fails and leaves a
    # half-written client. Point it at the nixpkgs prisma-engines package
    # globally so every shell/process (pnpm install, predev, process-compose)
    # has a valid engine. nix-resolved → no stale /nix/store hash, tracks
    # `af-rebuild`. Must match @prisma/client's major (currently 6.x).
    PRISMA_QUERY_ENGINE_LIBRARY = "${pkgs.prisma-engines_6}/lib/libquery_engine.node";
    PRISMA_SCHEMA_ENGINE_BINARY = "${pkgs.prisma-engines_6}/bin/schema-engine";
    PRISMA_QUERY_ENGINE_BINARY = "${pkgs.prisma-engines_6}/bin/query-engine";
    PRISMA_FMT_BINARY = "${pkgs.prisma-engines_6}/bin/prisma-fmt";
  };

  # home.sessionVariables above only reach interactive/login shells. The Chill
  # Subs + Galley dev suite runs under `systemd --user` (cs-galley-suite.service
  # → process-compose), which does NOT source hm-session-vars.sh, so without this
  # process-compose and its children (pnpm predev → `prisma generate`) had no
  # PRISMA_* and fell back to fetching a linux-nixos engine that 404s. The
  # systemd user manager loads ~/.config/environment.d/*.conf via
  # 30-systemd-environment-d-generator, so this makes the engine paths available
  # to every user service. Paths reference pkgs.prisma-engines_6 → gcrooted,
  # tracks af-rebuild. Apply to a running session without relogin via:
  #   systemctl --user import-environment   (after a daemon-reexec), or relogin.
  home.file.".config/environment.d/10-prisma.conf".text = ''
    PRISMA_QUERY_ENGINE_LIBRARY=${pkgs.prisma-engines_6}/lib/libquery_engine.node
    PRISMA_SCHEMA_ENGINE_BINARY=${pkgs.prisma-engines_6}/bin/schema-engine
    PRISMA_QUERY_ENGINE_BINARY=${pkgs.prisma-engines_6}/bin/query-engine
    PRISMA_FMT_BINARY=${pkgs.prisma-engines_6}/bin/prisma-fmt
  '';

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

  # Manual test runner — run the backend suite on demand (no CI gate).
  # Usage: af-test                 # full suite
  #        af-test -k test_nudge   # filter
  #        af-test tests/test_api.py
  home.file.".local/bin/af-test" = {
    executable = true;
    text = ''
      #!/usr/bin/env bash
      set -euo pipefail

      REPO_DIR="/data/ardent-forge/repo"
      cd "$REPO_DIR"

      echo "Running backend test suite (uv run pytest)..."
      exec uv run pytest "$@"
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
