# Alert triage playbook

Read by the unattended triage run. Each entry is a *signature* (the alert name
as it arrives from Grafana), the tier it may be handled at, and how to tell the
real thing from something that merely looks like it.

## Tiers

- **T0 ignore** — test/synthetic, flapping, already handled.
- **T1 diagnose only** — gather evidence, post findings, change nothing.
  **This is the default. Anything not listed below is T1.**
- **T2 operational** — an idempotent, reversible action on non-versioned state
  (e.g. regenerating a gitignored client). No repo change, so no PR.
- **T3 code fix** — a change to a tracked file, landed as a PR. Requires
  `nixos-rebuild build` to pass first.
- **T4 escalate** — notify and stop. Do not touch.

## Before anything: is the failure real?

The alert body carries the rule's annotation summary, **not** the log line that
tripped it. A marker in the log therefore never reaches the notification, and a
synthetic alert is indistinguishable from a real one at this level -- measured,
not assumed. So always confirm against source before acting:

    curl -sG http://127.0.0.1:3100/loki/api/v1/query \
      --data-urlencode 'query=<the rule expression from monitoring.nix>'

If the underlying log lines say SYNTHETIC, or the condition is already false,
this is T0. Say so and stop.

---

## typesense reindex failing

Mongo -> Typesense reindex loop failing. Submitter search drifts from the editor.

**First check** the indexer's own log, not the journal -- an unscoped
`journalctl | grep '[reindex] FAILED'` also matches Grafana's own log lines,
which quote the query expression. That mistake was made once already:

    tail -50 ~/Projects/Chill-Subs+Galley/t-eckert/csg/dev-suite/logs/typesense-indexer.log

**Known cause (T2).** `Unknown field <x> for select statement on model <Y>` means
the generated Prisma client is older than `prisma/schema.prisma`. Compare mtimes
of `typesense-indexer/prisma/schema.prisma` against
`typesense-indexer/node_modules/.prisma/client/schema.prisma`.

The regenerate is *not* a plain `prisma generate`. This package pins
@prisma/client 4.9.0, while the box's global PRISMA_* vars point at
prisma-engines_6. Mixing them fails in three different ways (CDN 404 on
prisma-fmt; 404 on migration-engine / introspection-engine, which v6 does not
ship; and `NodeAPIQueryEngineLibrary.dmmf is not a function` from the v6
library). Use the Prisma-4 bundle the dev suite already references:

    cd <repo>/chill-subs/typesense-indexer
    set -a; . <(grep -E '^PRISMA_' <suite>/env/typesense-indexer.env); set +a
    npx prisma generate

Verify: `lastAuditDate`-style field present in `node_modules/.prisma/client/index.d.ts`,
the 4.9.0 engine binary unchanged (checksum before/after), then watch for
`[reindex] ok` on the next cycle. The loop re-execs node each cycle, so it
self-heals within ~60s with no restart.

This touches only gitignored `node_modules`. **No PR. Never push chill-subs.**

**Recurrence.** `typesense-reindex.sh` runs `npm install` only when
`node_modules` is absent, so it never regenerates on a schema change. Any schema
edit reintroduces this. A durable fix there is T3 and belongs in the csg repo.

---

## systemd unit failed

`sum(node_systemd_unit_state{state="failed"}) > 0`.

Identify with `systemctl --failed`. Read the unit's journal before concluding
anything. Restarting a unit to clear the alert without understanding why it
failed is **not** a fix and is not permitted -- one of these sat failed for
three weeks and the useful information was in the failure, not the restart.

Diagnose (T1) unless the cause matches a known code fault, in which case T3.

---

## root filesystem above 80%

**T4 escalate, always.** Report the largest consumers and stop. Deleting to free
space unattended is not worth the risk of removing something that mattered.
Journals are the usual culprit (`journalctl --disk-usage`).

---

## prometheus target down

`count(up{job!="galley"} == 0) > 0`.

Which target, and is the underlying service actually down or just unscrapable?
T1 unless it is a config fault in `monitoring.nix`, which is T3.

---

## Repo rules

- **chill-subs** — `main` deploys straight to production. PR only, never a
  direct push, and never a merge. T2 there is limited to gitignored state.
- **ardent-forge** — PR when unattended, even though direct pushes are normal
  interactively. A PR that does not build must not be opened.
- **dotfiles** — PR. It is consumed as a flake input by this box and by the Mac.

## Always

State what was verified and how, the way the commits in these repos do. If the
evidence does not support a conclusion, say that instead of reaching for one.
