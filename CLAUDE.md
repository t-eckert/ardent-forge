# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Ardent Forge is the NixOS configuration for a single Bee Link box, reached over Tailscale. It exists to be a good place to do development work: a full toolchain preinstalled, long-running Claude Code sessions over SSH/mosh, dev servers shared to the tailnet, and monitoring so it's clear what the box is doing.

It is a config repo. There is no application here — no build, no test suite, no CI. The only thing that "runs" it is `nixos-rebuild`.

The repo used to also host an agentic task-management platform (a Python backend and a SvelteKit UI). That was removed on 2026-08-03; the concept is being rebuilt separately. If you find a reference to `forge/`, `ui/`, `uv run forge`, port 7030, or a `FORGE_*` env var, it's residue — delete it.

## Working on this repo

**This checkout is the deployment.** `/data/ardent-forge/repo` is what `nixos-rebuild` reads. Do not clone the repo elsewhere on the box to work on it — a second checkout means rebuilding from a tree that isn't the deployed one. `nix/locals.nix` deliberately omits this repo from `workspaceRepos` for that reason.

```bash
# Check that a change evaluates (fast, no switch)
nix build '/data/ardent-forge/repo/nix#nixosConfigurations.ardent-forge.config.system.build.toplevel' \
  --dry-run --impure --no-link

# Apply it
sudo nixos-rebuild switch --flake /data/ardent-forge/repo/nix#ardent-forge --impure

# Or: update flake inputs first, then switch, falling back to `boot` if the
# live switch can't be done (see nix/home.nix)
af-rebuild
```

`--impure` is mandatory: `nix/flake.nix` imports `nix/locals.nix` by absolute path.

`nix/locals.nix` is gitignored — it holds the username, tailnet domain, SSH keys, and the workspace repo list. `nix/locals.example.nix` is its committed template; keep the two in sync when adding a field.

Formatting is nixfmt-rfc-style, but only some files have been through it. Match the file you're editing rather than reformatting it wholesale in an unrelated change.

## Layout

- `nix/flake.nix` — inputs (nixpkgs unstable, home-manager, the `t-eckert/dotfiles` flake) and the `ardent-forge` host
- `nix/configuration.nix` — system module: boot, networking, firewall, Tailscale, users, SSH, mosh, podman, nix-ld, system packages, `/data` tmpfiles
- `nix/hardware.nix` — Bee Link specifics. Mounts are by **label**, not UUID; don't paste in a raw `nixos-generate-config` dump
- `nix/home.nix` — home-manager: the dotfiles home env plus the toolchains this box needs (uv, pyright, rust-analyzer, playwright, cargo-watch) and the OpenSSL/Prisma/Playwright env they depend on. Also defines `af-rebuild`
- `nix/services/*.nix` — one module per service
- `grafana/dashboards/` — dashboard JSON, read live off this checkout by Grafana's file provider
- `scripts/syncshot.py` — the notebook sync loop, run by `ardent-forge-notebook-sync`

## Services

| Unit | What |
|---|---|
| `caddy` | Tailnet front door. Serves a generated landing page at the bare domain, `/svc/{grafana,prometheus,ntfy}`, and one tsnet node per entry in `csApps` plus the `drop` WebDAV share |
| `postgresql` | Postgres 17 at `/data/postgresql`; `grafana` DB + exporter on :9187 |
| `prometheus` / `grafana` / `loki` / `alloy` | Metrics, dashboards, logs (`nix/services/monitoring.nix`) |
| `ollama` | CPU-only local inference on :11434. No models are pulled declaratively — `ollama pull <model>` as needed |
| `ntfy` | Push notifications, podman container on :8090 |
| `the-weather` | `ghcr.io/t-eckert/the-weather` container on :8091 |
| `marimo` | Headless marimo on :2718 against `~/Repos/lab`, exposed as `lab.<tailnet>` |
| `thomaseckert-dev` | Astro dev server on :10000, exposed as `te.<tailnet>` |
| `ardent-forge-notebook-sync` | Clones `t-eckert/Notebook` to `/data/ardent-forge/notebook` and runs `scripts/syncshot.py` every 30s |
| `workspace-init` | Clones `locals.workspaceRepos` into `~/Repos/github.com/owner/repo` at boot. Re-run with `sudo systemctl start workspace-init` |

Adding a tailnet host is a single entry in `csApps` in `nix/services/caddy.nix` — that drives the tsnet node, the vhost, and the landing-page listing together. Don't use `tailscale serve`; it conflicts with Caddy's management of the host domain.

## Secrets

No secret is ever committed or written to the Nix store. Two layers:

1. `/etc/ardent-forge/op-token` holds `OP_SERVICE_ACCOUNT_TOKEN`. It is placed **by hand** on the box, not by Nix, and is what lets services call `op`.
2. Each service that needs credentials runs under `op run --env-file <file>`, where the env file contains `op://` **references only** and is committed. See `nix/services/workspace-init.env` and `nix/services/notebook-sync.env`.

To give a service a new secret, add the reference to its env file — never the value.

## Deployment

There is no CI and no autodeploy. A push to `main` does nothing on its own; changes land when someone runs a rebuild on the box. Verify with the dry-run build above before switching, and check `systemctl list-units --failed` after.

`/data/` is the persistent state root and is not managed by git: `/data/ardent-forge/notebook` (the Obsidian vault clone), `/data/postgresql`, `/data/grafana`, `/data/prometheus`, `/data/loki`, `/data/ntfy`.
