![Logo for the Ardent Forge project](./assets/AF.svg)

# Ardent Forge

Hey — welcome to my workshop.

I've spent a lot of years tuning the way I write code: the tools I reach for, the habits, the little machines that quietly take the boring parts off my plate. Ardent Forge is where a good chunk of that lives now. It's a control plane I run on a small NixOS box at home, and I can get to it from anywhere over Tailscale. I hand it work — a message in a chat thread, a Linear issue, something on a schedule — and it spins up Claude Code sessions to actually do it in my repos. I also can SSH in for a full coding environment with all of my tools pre-installed. When I run a dev server, it gets shared over Tailscale.

It's built for me, so it's full of my particular choices. But you're welcome to poke around. If a piece of it is useful, take it and make your own.

## The gist

There's one agent in charge — *Ardent Forge* itself — and it coordinates a handful of smaller, more specialized agents. I talk to the leader, and it figures out which agent should pick up the job.

Work comes in from three places — a chat thread, a Linear issue tagged with a `claude` label, or a cron schedule — and turns into a **task**. Tasks are the thing everything revolves around. They get written to a local SQLite database the moment they show up, and the system saves their progress as they go, so a restart never drops anything and a task that got interrupted can carry on from where it stopped.

## How it works

### The loop

A coordinator runs one steady loop. Every tick it checks Linear for new issues, fires off any schedules that are due, and works through the queue of waiting tasks. Tasks I start from chat can wake the loop up early so they feel responsive, while the background pollers stay on a slower beat. It's a small, readable core — one loop, one queue, nothing clever.

### The task pipeline

Each task moves through a few stages:

```
queued → triaging → executing → verifying → delivering → completed
                                                          ↑
failed ──────────────────────────── requeue ──────────────┘
```

Any stage can fail, and a failed task can get requeued for another try. The transitions are checked, so a task can't wander into a state that doesn't make sense.

### Agents

An agent is a worker that knows how to take a task through the pipeline. The nice part is that agents only sign up for the stages they need — one might just `execute`, another runs the whole sequence — and the coordinator skips the rest. So agents stay small.

Here's who's around right now:

- **Code** — the one that does most of the work. It clones the repo, runs Claude Code in a live [Zellij](https://zellij.dev) session I can attach to and watch, checks the result, and opens a pull request.
- **Plan** — the self-builder. It reads a spec, writes up an implementation plan, and commits it back.
- **Tickets** — keeps Linear in sync as things move.
- **Echo** — a little debug agent that just echoes back. Handy for poking at the loop.

When I want a new capability, I write a new agent. That's pretty much the whole story.

### Connectors

Agents don't reach out into the world on their own — they ask **connectors** for tools. A connector wraps something external and hands it over as a tool an agent (or the chat) can call. Each agent says which connectors it wants, and it gets exactly those and nothing else.

Right now they cover things like pulling secrets from 1Password, web search, a read-only window into my notebook, and a little watcher that checks my bandwidth now and then.

### The box

A few habits keep the machine itself simple, and these are the bits I'd most recommend borrowing:

- **The box is nukable.** Nothing precious lives on it. Repos clone fresh from GitHub, and a rebuild doesn't cost me anything.
- **Secrets stay in 1Password.** Decrypted values never touch the disk — they're resolved right when a task starts, and each repo only gets to see the secrets it's declared.
- **Zellij so I can watch.** Because code work runs in a named session, I can SSH in and watch an agent work in real time. I can also just grab the controls and do my own development.
- **Tailscale is the front door.** The whole thing lives on my tailnet, so there's no auth layer to build and nothing sitting out on the public internet, but I can also open a funnel to particular ports if I need to.

## Have a look around

This repo is meant to be read. If you want to see the loop actually turn, start at `forge/coordinator.py`. The agent contract is in `forge/agents/`, connectors live in `forge/connectors/`, and the pipeline's state machine is one small file at `forge/state.py`. `CLAUDE.md` is my working map of the codebase, and the thinking behind the design is kept in `docs/superpowers/specs/`.

Thanks for stopping by. If any of it helps you build your own thing, that's the best outcome I could ask for.
