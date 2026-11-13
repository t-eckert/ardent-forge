# AGENTS.md

Guidance for coding agents working in this repository. `CLAUDE.md` imports this file, so there is one copy to maintain.

## Project

Ardent Forge is the NixOS configuration for a single Bee Link box, reached over Tailscale. It exists to be a good place to do development work: a full toolchain preinstalled, long-running Claude Code sessions over SSH/mosh, dev servers shared to the tailnet, and monitoring so it's clear what the box is doing.

It is a config repo. There is no application here — no build, no test suite, no CI. The only thing that "runs" it is `nixos-rebuild`.

The repo used to also host an agentic task-management platform (a Python backend and a SvelteKit UI). That was removed on 2026-08-03; the concept is being rebuilt separately. If you find a reference to `forge/`, `ui/`, `uv run forge`, port 7030, or a `FORGE_*` env var, it's residue — delete it.

## Working on this repo

**A push to `main` deploys the box.** `af-rebuild.service` (`nix/services/deploy.nix`) checks `origin/main` every two minutes and deploys that exact commit as root from its own clone; nothing builds from a working tree. Develop in `~/Repos/github.com/t-eckert/ardent-forge`. Ask before pushing to `main`. Claude Code sessions are made to ask by `.claude/settings.json`; other agents have to do it themselves.

After a switch it checks tailscaled, sshd, Tailscale being online and GitHub being reachable. Each is a way back into the box, so if any fails for a minute it switches back to the previous system. Units that newly fail are reported and kept. A failed commit is skipped until `main` moves. Results go to the `ardent-forge-deploys` ntfy topic. The design and its reasons are in `nix/services/deploy/af-deploy.py`.

The pre-push hook (`.githooks/pre-push`) builds the exact commit being pushed to `main`, so a broken config never reaches it and the deploy finds the build already done. Enable it in a new clone with `git config core.hooksPath .githooks`; `git push --no-verify` skips it.

```bash
af build                 # build the checkout's system; says if it matches what's running
af update [input...]     # update flake inputs and build; review, commit, push
af pins [--update]       # pins kept outside flake.lock (caddy plugins, image digests)

af status                # running commit, origin/main, last result, reboot pending
af deploy [--retry]      # deploy origin/main now instead of waiting for the timer
af log [N]               # deploy journal
af config show|edit      # /etc/ardent-forge/locals.json; edit deploys after
af repos list|sync       # repos workspace-init clones into ~/Repos/github.com
af repos add|remove o/r  # edit that list (a 1Password note) and sync
```

Updating an input is a change like any other: `af update dotfiles` after pushing to t-eckert/dotfiles, then commit the lock and push. Nothing updates inputs on its own.

`--impure` is mandatory: `nix/flake.nix` reads `/etc/ardent-forge/locals.json` by absolute path.

Host values are not in the repo. `/etc/ardent-forge/locals.json` (root-owned) holds the username, tailnet domain and SSH keys, read by the build as plain JSON; `nix/locals.example.json` is its committed template, so keep the two in sync when adding a field. The workspace repo list is not on the box or in the repo at all: it is the `workspace-repos` Secure Note in the `Ardent Forge` 1Password vault (one `owner/repo` per line), because this repo is public and private repo names should not land here by accident. workspace-init reads it at runtime and the build never sees it. Never commit repo names to stand in for it.

Formatting is nixfmt-rfc-style, but only some files have been through it. Match the file you're editing rather than reformatting it wholesale in an unrelated change.

## Layout

- `nix/flake.nix` — inputs (nixpkgs unstable, home-manager, the `t-eckert/dotfiles` flake) and the `ardent-forge` host
- `nix/configuration.nix` — system module: boot, networking, firewall, Tailscale, users, SSH, mosh, podman, nix-ld, system packages, `/data` tmpfiles
- `nix/hardware.nix` — Bee Link specifics. Mounts are by **label**, not UUID; don't paste in a raw `nixos-generate-config` dump
- `nix/home.nix` — home-manager: the dotfiles home env plus the toolchains this box needs (uv, pyright, rust-analyzer, playwright, cargo-watch) and the OpenSSL/Prisma/Playwright env they depend on
- `nix/services/*.nix` — one module per service
- `grafana/dashboards/` — dashboard JSON, read live off this checkout by Grafana's file provider
- `scripts/syncshot.py` — the notebook sync loop, run by `ardent-forge-notebook-sync`

## Services

| Unit | What |
|---|---|
| `caddy` | Tailnet front door. Serves a generated landing page at the bare domain, `/svc/{grafana,prometheus,ntfy}`, and one tsnet node per entry in `csApps` plus the `drop` WebDAV share |
| `postgresql` | Postgres 17 at `/data/postgresql`; `grafana` DB + exporter on :9187 |
| `prometheus` / `grafana` / `loki` / `alloy` | Metrics, dashboards, logs (`nix/services/monitoring.nix`) |
| `ntfy` | Push notifications, podman container on :8090 |
| `the-weather` | `ghcr.io/t-eckert/the-weather` container on :8091 |
| `marimo` | Headless marimo on :2718 against `~/Repos/lab`, exposed as `lab.<tailnet>` |
| `thomaseckert-dev` | Astro dev server on :10000, exposed as `te.<tailnet>` |
| `ardent-forge-notebook-sync` | Clones `t-eckert/Notebook` to `/data/ardent-forge/notebook` and runs `scripts/syncshot.py` every 30s |
| `workspace-init` | Clones the repos in the `workspace-repos` 1Password note into `~/Repos/github.com/owner/repo` at boot, keeping a copy of the list in `/var/lib/workspace-init/repos`. Re-run with `af repos sync` |

Adding a tailnet host is a single entry in `csApps` in `nix/services/caddy.nix` — that drives the tsnet node, the vhost, and the landing-page listing together. Don't use `tailscale serve`; it conflicts with Caddy's management of the host domain.

## Secrets

No secret is ever committed or written to the Nix store. Two layers:

1. `/etc/ardent-forge/op-token` holds `OP_SERVICE_ACCOUNT_TOKEN`. It is placed **by hand** on the box, not by Nix, and is what lets services call `op`.
2. Each service that needs credentials runs under `op run --env-file <file>`, where the env file contains `op://` **references only** and is committed. See `nix/services/workspace-init.env`.

To give a service a new secret, add the reference to its env file — never the value.

A token must not reach `.git/config` either. Don't put it in a clone URL (git saves the URL), and don't expand it into a configured credential helper; have the helper read the variable when git runs it, as `workspace-init.nix` does. A long-running service should not hold the token at all: notebook-sync and lab-sync ask 1Password through `nix/services/github-pat-credential.nix` whenever git needs it, so rotating `github-pat` needs no restart.

## Deployment

A push to `main` is a deploy: `af-rebuild.service` picks it up within two minutes (see "Working on this repo" above). There is no CI; `af build`, which the pre-push hook also runs, is the check before pushing. After it lands, `af status` shows the running commit, the result and whether a reboot is pending; `af log` has the details and any units that newly failed.

`/data/` is the persistent state root and is not managed by git: `/data/ardent-forge/notebook` (the Notebook clone), `/data/postgresql`, `/data/grafana`, `/data/prometheus`, `/data/loki`, `/data/ntfy`.
