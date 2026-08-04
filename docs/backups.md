# Backups

## Where this stands

| Data | Protected against fat-fingers | Protected against the disk dying |
|---|---|---|
| Postgres (`grafana`, `ardent_forge`) | yes — nightly dumps | **no** |
| `/data/ardent-forge/notebook` | yes | yes — git, pushed to GitHub every 30s |
| `/data/ardent-forge/repo` | yes | yes — git, **except `nix/locals.nix`** |
| `/data/grafana` (secret_key, plugins) | no | **no** |
| `/data/loki`, `/data/prometheus` | no | **no** — deliberate, see below |
| `/data/ntfy` | no | **no** |

Nothing on this box survives the NVMe failing, apart from what git pushes
off it. That is the gap to close, and it needs a credential that has to be
created by hand — see "Adding off-box backups" below.

## What runs today

`postgres-dump.timer` fires at 03:15 with a 5 minute jitter, `Persistent=true`
so a missed run catches up. It dumps every non-template database to
`/data/backup/postgres/<db>-<timestamp>.dump` in custom format and deletes
dumps older than 14 days.

Logical dumps, not a copy of `/data/postgresql`: file-level copies of a running
cluster are not crash-consistent and restore to a corrupt cluster. Dumps are
also what an off-box backup should ship, so this is a prerequisite for restic
rather than a detour around it.

A failure surfaces through the `systemd unit failed` alert. That is the point —
a backup that stops silently is worse than no backup, because it is trusted.

Run it by hand:

```bash
sudo systemctl start postgres-dump
ls -la /data/backup/postgres/
```

Restore one database:

```bash
sudo -u postgres pg_restore --clean --if-exists -d grafana \
  /data/backup/postgres/grafana-20260804T031500Z.dump
```

## The `locals.nix` problem

`nix/locals.nix` is gitignored by design — it holds the username, tailnet
domain, SSH keys and workspace repo list. `--impure` is mandatory precisely
because the flake reads it by absolute path.

It exists in exactly one place: this disk. The entire configuration is on
GitHub and **the machine still cannot be rebuilt without this file**. It is
854 bytes and it is the single point of failure for an otherwise fully
declarative system.

Copying it to another path on the same NVMe achieves nothing against disk
failure. It needs to leave the box. Reasonable options, in rough order of
effort:

1. A 1Password item in the `Ardent Forge` vault — consistent with how every
   other secret here is handled, and `op` is already installed.
2. A private git repo, encrypted with `age` or `sops`.
3. Anywhere off the box at all. A file this small on a USB key beats what is
   there now, which is nothing.

`nix/locals.example.nix` is committed and lists every field, so a rebuild from
scratch is a matter of filling in values rather than reverse-engineering them —
but the SSH keys are not recoverable from the template.

## Why Loki and Prometheus are not backed up

Both are observability data about this box, both are now retention-bounded
(30 days each), and both are regenerable in the sense that matters: losing
them costs history, not function. They are also the two largest consumers of
`/data`. Backing them up would dominate the backup while protecting the least
valuable thing on the disk.

If the history does matter to you, they are ordinary directories and can be
added to the restic paths below.

## Adding off-box backups

Not done, because it needs a repository password and remote credentials that
cannot be created unattended. The shape it should take, following the
convention already used by `workspace-init.env` and `notebook-sync.env` —
secrets are `op://` references, never values:

1. Create a 1Password item in the `Ardent Forge` vault, e.g. `restic-ardent-forge`,
   with a generated `password` field and the remote's credentials.

2. Add `nix/services/restic.env` containing references only:

   ```
   RESTIC_PASSWORD=op://Ardent Forge/restic-ardent-forge/password
   B2_ACCOUNT_ID=op://Ardent Forge/restic-ardent-forge/account-id
   B2_ACCOUNT_KEY=op://Ardent Forge/restic-ardent-forge/account-key
   ```

3. A `services.restic.backups.<name>` entry run under `op run --env-file`,
   backing up:

   - `/data/backup/postgres` — the dumps, not the live cluster
   - `/data/grafana` — `secret_key` and plugins
   - `/data/ntfy/etc`
   - `nix/locals.nix`

   with `pruneOpts` along the lines of `--keep-daily 7 --keep-weekly 5
   --keep-monthly 12`.

4. Point the `systemd unit failed` alert at it by doing nothing — a failing
   restic timer enters the failed state and is picked up automatically.

The one thing worth insisting on: **test a restore before trusting it.**
`restic restore` into a scratch directory and diff. An untested backup is a
belief, not a backup.
