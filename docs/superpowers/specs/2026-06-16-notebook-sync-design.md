---
title: Consolidate Notebook onto a single git sync plane
date: 2026-06-16
status: draft
area: notebook
---

# Consolidate Notebook onto a single git sync plane

## Problem

The Notebook (Obsidian vault, `github.com:t-eckert/Notebook.git`) is synced across
four devices through **two independent sync planes**:

- **git** via Syncshot → GitHub: AF box (`/data/ardent-forge/notebook`, `syncshot.py
  --period 30`) and the personal Macbook.
- **Obsidian Sync** (Obsidian's hosted relay): personal Macbook, work Macbook, iPhone.

The only device bridging the two planes is the **personal Macbook**, which runs both.
When it is closed (most of the time):

- Edits made on the iPhone or work Macbook reach Obsidian Sync but never reach GitHub,
  so the **Ardent Forge UI shows stale data**.
- AF-side writes reach GitHub but do not reach the iPhone/work Macbook until the
  personal Macbook wakes and re-bridges.

Running Syncshot *and* Obsidian Sync on the same files also risks the two planes racing
and clobbering each other — the fundamental hazard of having two sync mechanisms mutate
the same working tree.

## Goal

Collapse to a **single sync plane (git)** with GitHub as the single source of truth, so
the AF box stays current regardless of which device made an edit, and there is no
cross-plane clobbering. Realtime propagation to the iPhone is explicitly **not**
required.

## Decisions

- **Direction:** Consolidate onto git. Obsidian Sync is retired on all devices.
- **iPhone client:** **Working Copy** (native libgit2 git client), not the Obsidian Git
  community plugin. Rationale below.
- **Scope:** Sync plane only. Repo-size/history work is out of scope.

### Why Working Copy and not the Obsidian Git plugin

The vault is large: **~1.3 GB working tree, 10,199 tracked files, 4,705 markdown notes,
and a ~950 MB `.git` history across 6,508 commits**, including multi-MB binary image
assets under `+Assets/`.

The Obsidian Git plugin on iOS uses `isomorphic-git`, a pure-JavaScript git
implementation that works only on small vaults. At ~950 MB of history it is expected to
be unusably slow or to run out of memory on an iPhone — the initial clone alone is
prohibitive. Working Copy uses a native libgit2 engine that handles repos this size
comfortably, supports background fetch, and has a real conflict-resolution UI. Obsidian
opens the vault directly from Working Copy through the iOS Files provider.

## Target architecture

GitHub (`t-eckert/Notebook`) is the single source of truth. Every device is a git
participant; there is exactly one sync plane.

| Device         | Sync mechanism                                  | Obsidian Sync |
| -------------- | ----------------------------------------------- | ------------- |
| AF box         | `syncshot.py --period 30` (unchanged)           | n/a           |
| Personal Mac   | Syncshot (existing)                             | **disabled**  |
| Work Mac       | Syncshot (**newly added**)                      | **disabled**  |
| iPhone         | Working Copy clone + Obsidian via Files provider | **disabled**  |

### Per-device changes

- **AF box** — no change. Continues running `syncshot.py --period 30` against
  `/data/ardent-forge/notebook`.
- **Personal Mac** — keep existing Syncshot setup; disable Obsidian Sync for this vault.
- **Work Mac** — add Syncshot (same script + launchd agent as the personal Mac); disable
  Obsidian Sync for this vault.
- **iPhone** — install Working Copy; clone the repo into it; point Obsidian at the
  Working Copy repo via the iOS Files provider. Configure a **Shortcuts automation** that
  runs Working Copy "pull, then commit + push" on Obsidian backgrounding and on a periodic
  timer, so phone edits reach GitHub (and therefore AF) within minutes. Realtime is not a
  requirement.

## Cutover / migration

This is the data-loss-sensitive step. Before disabling Obsidian Sync anywhere, **flush
both planes into git**:

1. Open Obsidian on the personal Macbook and let it fully sync **down** from Obsidian
   Sync (so any iPhone/work-Mac edits still living only in Obsidian Sync land in the
   working tree).
2. Let Syncshot commit and push everything, then confirm `git status` is clean and the
   GitHub `main` matches the local tree.
3. Only then disable Obsidian Sync on the personal Mac, work Mac, and iPhone.
4. On the work Mac, install/start Syncshot and confirm it pulls cleanly.
5. On the iPhone, clone fresh into Working Copy and re-point Obsidian at it.

Skipping step 1–2 risks losing edits that were sitting in Obsidian Sync but never bridged
to git.

## Conflict behavior (known limitation)

Syncshot commits every 30s and runs `git pull --rebase` when the local clone has
diverged, but it has **no rebase-conflict handling**. If the same note is edited on two
machines within the same sync window, a rebase can stall and leave that clone wedged until
manually resolved. For a single user this is rare, but the plan documents recovery rather
than pretending it cannot happen.

**Un-wedging a stalled clone** (manual recovery on the affected device):

```bash
cd <clone>
git rebase --abort           # back to a known state
git stash                    # set aside local edits if any
git pull --rebase            # should now fast-forward
git stash pop                # reapply, resolve any conflict by hand
```

Hardening `syncshot.py` itself (e.g. auto-resolving or quarantining conflicts) is **out
of scope** — it is vendored and updated upstream.

## Out of scope

- Slimming the ~950 MB history / `+Assets/` binary bloat. This is real and affects every
  clone, but it is a separate effort (gitignore/relocate assets, optional history
  rewrite). Noted as a future improvement.
- Changes to AF's `NotebookReader` / `NotebookWriter` — they continue to operate against
  the local clone unchanged.
- Modifying the vendored `scripts/syncshot.py`.

## Success criteria

- Obsidian Sync is disabled on all three Apple devices; no device runs two sync planes.
- An edit made on any device (including the iPhone, after its Shortcut fires) appears on
  the AF box / AF UI without the personal Macbook needing to be awake.
- No cross-plane clobbering, because there is only one plane.
