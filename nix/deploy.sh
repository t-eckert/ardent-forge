#!/usr/bin/env bash
set -euo pipefail
cd /data/ardent-forge/repo
git pull
sudo nixos-rebuild switch --flake ./nix#ardent-forge --impure
