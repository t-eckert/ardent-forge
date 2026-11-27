# The implementer: design

The implementer is the Forge's coding agent. A ticket delegated to it in Linear becomes a pull request. Its scope is the whole Forge: it can work on any repo it is configured for, and everything specific to one repo lives in that repo.

The code started on 26 November 2026 as a copy of an earlier agent's implementer. Some of this design is carried over from there and still has to be revised; those places say so.

## Implementing tickets

**The implementer is an agent in Linear, so a ticket is delegated to it the way a person is assigned.** The delegation starts a run. The implementer starts a Claude Code session against the ticket, and the session does the coding. The implementer itself orchestrates and does not write code.

- Starts from: a Linear delegation
- Produces: a pull request, plus progress posted back to the ticket

**The implementer is a Linear agent app.** On Linear's agent platform, delegating an issue opens an agent session and sends a webhook. The person who delegated stays the assignee. The agent posts its progress into the issue as agent activities.

**A run, in order:**

1. **Acknowledge within 10 seconds.** Linear expects a first activity within 10 seconds of a session opening. The gateway forwards the event at once, and the implementer posts a `thought` before doing anything slow. The gateway itself makes no outbound calls.
2. **Check the limits.** If the implementer already has the repo's cap of open pull requests, it answers on the ticket with that reason and stops. It does not queue the ticket.
3. **Ask if the ticket is too vague.** If the ticket does not say enough to implement, the implementer posts specific questions on it and waits for an answer before starting. The run stays open while it waits, and it survives restarts.
4. **Prepare a worktree and a session container.** The container gets the worktree and nothing else from the host. See "Isolating a session" below.
5. **Run Claude Code** on the ticket, inside the container, with a prompt built from the ticket and the repo's conventions.
6. **Run the repo's checks inside the same container, and retry fixes.** The checks run in order, and the run stops at the first failure. The implementer then reruns Claude Code with a fix prompt, up to the repo's attempt limit. The implementer never executes a check itself. It only reads each check's exit code and output.
   - The fix prompt carries every previous attempt, not only the last one, so the session can see what it already tried.
   - Failing output is truncated from the start, keeping the end, because compilers put the useful part last.
   - Total wall-clock time is capped across all attempts, not just per attempt. The elapsed time and the attempt count are saved in the run's checkpoint, so a restart does not reset them.
   - The run ends `verified` or `unverified`, and that verdict is carried into the pull request.
7. **Review the diff.** One direct model call, not a Claude Code session, reads the ticket, the diff and the repo's `CLAUDE.md`. It returns findings, each with a file, a line where possible, and a severity. The findings go in the pull request body as advice for the reviewer. They never start another fix round. A run that is unverified, or a diff too small to say anything about, skips the review and says why.
8. **Open the pull request.** The implementer pushes the branch and opens the pull request. It pushes with git hooks disabled (`core.hooksPath=/dev/null`), so nothing a session wrote runs with the implementer's credentials. The body says what was verified and what was not, and carries the check output when the run is unverified.
9. **Report back.** Each milestone is posted on the ticket as an activity: started, verifying, pull request opened with its link, or the reason it stopped.

**Rules carried over from earlier attempts:**

- **The Linear app installs with `actor=app`** and the `app:assignable` and `app:mentionable` scopes, so tickets can be delegated to it and it can be mentioned.
- **"Ran but changed nothing" is its own outcome.** A session that exits cleanly without a diff is reported as that, never as success.
- **Start with two prompts:** one to implement, one to fix. A third waits for a specific failure that needs it. An earlier agent grew nine, and that sprawl made it hard to reason about.
- **Transcripts stay out of SQLite.** Each session's transcript is a file in the run's directory. The database stores only its path, so the database stays small enough to inspect by hand.
- **Rebase on a freshly fetched base before pushing.** A conflict ends the run as a failure. The implementer does not try to resolve it.
- **An unverified pull request says so in its first line,** and carries a `needs-review` label.
- **It never approves or merges,** and its GitHub identity cannot push to a repo's default branch.

### Which repos it works on

**The implementer works only on repos it is configured for,** and each must have a policy file on its default branch. The list lives outside this public repo, as `workspace-repos` does, so private repo names never land here.

**The implementer never works on `ardent-forge`.** An agent editing the configuration of the box it runs on is a bootstrapping hazard, so it is refused explicitly, not left to routing.

### What each repo provides

**Everything specific to a repo lives in that repo:**

- **A policy file** that sets the checks to run, the base branch, the fix-attempt limit and the cap on open pull requests. It rejects unknown keys, so a typo cannot quietly change behaviour, and names the file and key in its error.
- **A session image:** a Containerfile holding the toolchains the repo's checks need, installed ahead of time, because a session cannot download a toolchain from behind the fence.
- **Checks that run offline.** A session never gets a database or other service of its own, so a repo whose checks need one makes them work without it.

**A policy file describes how to work in the repo, never what the implementer may access.** Access lives in the implementer's credentials and fence, so a pull request to a repo cannot widen its own reach.

**The implementer reads the policy file and the Containerfile from the default branch, never from the session's worktree.** A session can edit any file in its worktree. If the implementer read the worktree's copy, a session steered by a hostile ticket could rewrite a check command, and the implementer would then run it. The implementer keeps its own read-only checkout of each repo's default branch for this. Even then, the checks run only inside the session container, so a bad check command can do no more than the session could already do.

### Notifications

**Some moments push a notification through ntfy:**

- **A run failed or got stuck.** It ended unverified, ran out of budget, or a task was parked after repeated crashes.
- **The implementer needs input.** It asked a question on a ticket and is waiting.
- **System health.** A snapshot is stale, the gateway's spool is backing up, or the fence probe failed.

A pull request that is ready for review does not notify. It shows up in GitHub and on the ticket.

### Keys on external actions

**Every external action has a key, so a repeat finds the first one.** A run can repeat work after a crash, a deploy or a restore. These keys stop the repeat from becoming a duplicate:

- **Branches** are named `implementer/<ticket>`, for example `implementer/ABC-123`. Before opening a pull request, the implementer looks for an open one on that branch and reuses it.
- **Linear comments and activities** carry a hidden marker, `<!-- implementer:<run id>:<milestone> -->`. The implementer searches the ticket for the marker before posting.

## Isolating a session

**Each Claude Code session runs in its own rootless Podman container,** holding the worktree and nothing else from the host. It never sees the implementer's GitHub or Linear tokens, or any other run's state.

**The container shares the host's network namespace and goes out through the implementer's `crucible` proxy.** `crucible`'s allowlist is a proxy listening on the host's loopback address. A container with its own network namespace has its own loopback, so it could reach neither the proxy nor anything else, and the session would fail. So the container runs with `--network=host`, and `HTTP_PROXY` and `HTTPS_PROXY` point at the implementer's proxy.

**The allowlist is the Forge's, never a repo's.** It is set in the implementer's `crucible` profile in this repo, so a pull request to a repo cannot widen it. It holds the model API (`api.anthropic.com`), `github.com` for fetching only, since the session holds no token, and the package registries the configured repos need.

**The container's processes stay inside the implementer's systemd slice.** Podman runs with `--cgroups=split`, so the egress floor and the memory limits apply to the session as well. Rootless Podman under a system unit also needs:

- a fixed uid with lingering enabled, so `/run/user/<uid>` exists, and `XDG_RUNTIME_DIR` pointing at it
- subuid and subgid ranges
- `Delegate=yes` on the unit, for `--cgroups=split`
- `NoNewPrivileges` left off, since it stops the setuid `newuidmap` that rootless Podman runs

The NixOS module sets all four for the implementer only.

**The container holds as little as it can.** It runs as the implementer's own uid through `--userns=keep-id`, with every capability dropped and `no-new-privileges` set. It mounts the worktree at `/work` and the repo's build cache at `/cache`, and nothing else.

**A probe checks the fence from inside a container.** `implementer probe` passes only if `api.anthropic.com` is reachable through the proxy, a host off the allowlist is refused, and going around the proxy is refused. Outside the fence it fails, which is what it is for.

**One session runs at a time.** The Forge has 15 GiB of memory and 4 cores, and already uses about 7 GiB. Its memory limits cover only interactive users' slices, and system units are left uncapped on purpose. So:

- **Concurrency is 1,** fixed in the first version.
- **The implementer's unit has `MemoryHigh=4G` and `MemoryMax=5G`,** so a runaway build is throttled, then killed, before it touches interactive work. The heaviest checks measured so far, a Rust workspace's format, check and clippy, peaked at 3.1 GiB from a cold cache and 1.1 GiB warm, including the page cache.
- **Each repo gets a build cache,** under the implementer's state directory and mounted at `/cache`. Its session image points the toolchains' caches there. With one session at a time, the cache needs no locking.

**A session's container is labelled with its run id.** When the implementer starts, it removes every container labelled as its own, before its harness resumes. Nothing is running yet, so each such container was left by a crash, and a run that was cut off starts a fresh container on the same worktree when it resumes.

**Old worktrees, branches and sessions are cleaned up** once their run has ended.

## Hosting: the Forge, behind a Cloudflare Tunnel

**The implementer runs on the Forge.** A Cloudflare Tunnel gives Linear a public endpoint to send webhooks to, without opening a port on the Forge.

**The gateway is the only thing behind the tunnel.** It checks each webhook's signature, drops anything that fails, and hands the event to the implementer. It makes no outbound API calls itself, so a hole in the public surface reaches nothing but a hand-off.

**The gateway keeps a spool, so an event is never lost because the implementer is down.** Before it answers the sender, the gateway appends each verified event to an append-only file on disk and fsyncs it. Then it delivers the event over localhost, oldest first, and retries with backoff until the implementer accepts. While the implementer is draining, restarting or crashed, it simply receives its events late. The spool is the gateway's only state. Accepted events are marked done, and the file is rewritten without them once they pile up.

**Linear sends to `/linear/implementer`,** and the gateway checks the signature with the Linear app's signing secret. It then checks the signed `webhookTimestamp` is within a minute, as Linear recommends against replays. Anything that fails is answered `401` and never spooled.

**The implementer checks the signature again.** The hand-off carries the raw body and the sender's signature, and the implementer verifies it with its own copy of the webhook secret. So a local process that can reach its port cannot forge an event, and a compromised gateway can only pass on events the sender really signed. The implementer does not check the timestamp, since an event may have waited in the spool.

**An event the implementer refuses for good is dropped, not retried.** A `400`, `401` or `413` means retrying cannot help, most likely a mismatched secret. The gateway logs it and moves on, so one bad event does not block the queue behind it.

**Each event starts at most one run.** Pi Durable's `requestId` deduplicates submissions to a conversation, but a submission is model input and a webhook is not. So the implementer keeps its own record per delivery id. Reading that record and creating the event's task happen in one commit, so an event handed over twice, or by two requests racing, starts one task.

**The gateway restarts as little as possible.** The spool covers the implementer's downtime but not the gateway's own. For the few seconds the gateway is restarting, `cloudflared` cannot reach it, and Linear sees an error. Linear retries a failed webhook three times. Whether it redelivers an agent-session webhook is still open.

## Packaging and deploys

**The implementer lives in this repo and deploys with the Forge.** `nix/package.nix` builds it with Node 24, and `nix/module.nix` runs one systemd unit per process. A push to `main` deploys it, as it deploys everything else here.

**Not wired in yet.** Neither file is imported by the Forge's flake yet, and the module still expects one session image shipped inside the package. Both change to build each repo's image from that repo's Containerfile on its default branch. Where those image builds run, and with what egress, is still to design: a build downloads toolchains, which the session fence refuses.

**Each unit gets its own** 1Password env file with only the `op://` references it needs, a `crucible` profile with its egress allowlist, and a Unix user and state directory under `/data/implementer/<process>/`.

**A deploy restarts the implementer, and that is safe.** Each unit stops with SIGTERM, which starts the graceful exit below. Its `TimeoutStopSec` is set above the grace period plus the hard deadline, so the implementer ends itself.

**The implementer snapshots its database before it starts.** The unit runs `implementer backup --local implementer` first. A Pi Durable release can migrate the schema with no way back, so this snapshot is what makes rolling back a deploy safe. `--local` keeps the last few snapshots and prunes older ones. Shipping snapshots off the box is the Forge's job, still to build.

## Stack

**TypeScript on Node 24, with Pi Durable as the harness and SQLite for storage.** Pi Durable runs each run as a durable state machine and saves a checkpoint at every step, so a process killed partway through a ticket resumes from its last checkpoint. It lets one process own a storage at a time and does no locking between processes, so the implementer keeps its own lock.

**Models are reached with the implementer's own Anthropic API key.** Its Pi Durable conversations and its Claude Code sessions both use it, so each run's cost is the implementer's own and is tracked per run. The implementer passes the key into each session, which is the one credential a session holds.

## Graceful exit, with a timeout

**On SIGTERM or SIGINT, `implementer run <process>` drains and exits within a set time.** The grace period is `--grace`, 30 seconds by default. A deploy, a reboot and `systemctl stop` all send SIGTERM, so this is the normal way a process ends.

**A clean exit matters more than it looks.** Pi Durable counts each task that a crash cuts off, and parks a task after five such restarts. A clean `harness.close()` is not counted, but a SIGKILL is. So an implementer that is killed on every deploy would, after five deploys, park the long task it was in the middle of.

**The exit, in order:**

1. **Stop taking new work.** The local listener answers new events with `503`. The gateway keeps them in its spool and delivers them after the restart. The scheduler starts no new tasks.
2. **Let in-flight work reach a checkpoint.** Pi Durable saves a checkpoint at every step. Most steps are short, a model turn or an API call, and finish within the grace period.
3. **At the deadline, abort what is still running.** `harness.close()` signals every running tool to abort and waits for each to return. Work that is cut off stays pending in the database, and resumes on the next start.
4. **Close the database and release the lock,** then exit `0`.

**Every tool honours its abort signal promptly**, because `close()` waits for running tool code to return. The slowest is a Claude Code session, which can run for twenty minutes. On abort, its tool stops the session's container, with Podman's own short stop timeout, and returns. It leaves the worktree in place. The tool is declared safe to replay, so after a restart it runs a fresh session on the same worktree, which still holds what the first session wrote.

**A resumed session is told what came before.** Its prompt starts with the worktree's diff against the base branch and a note that an earlier session was interrupted, so it continues the work instead of starting over. Its time and attempt budget come from the checkpoint, so a run that straddles a deploy does not get a fresh budget.

**No container outlives its run.** On a graceful exit, the tool stops its container. After a crash, the implementer stops any leftover container when it next starts, by its run-id label.

**Two backstops:**

- **A hard deadline.** If `close()` has not finished within `--grace` plus 15 seconds, the process logs which tasks were still running and exits non-zero. The unit's `TimeoutStopSec` is set above that total, so the implementer ends itself and is not left to a SIGKILL.
- **A second signal exits at once.** It is for a person at a terminal who does not want to wait.

**Duplicate events are harmless.** The gateway may deliver an event the implementer had already accepted before it began draining, and a sender may redeliver one too. The implementer records each delivery id in the same commit that starts the event's task, so a repeated event finds the record and does not start a second run.
