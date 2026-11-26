---
name: spawn-tab
description: Open a new Zellij tab running its own interactive Claude Code session, started with a brief you write, for work Thomas will watch, steer or pick up from his phone. Use when Thomas says "open a tab for", "spawn a session", "start another session on", "put that in its own tab", or asks for a piece of work to run beside this one where he can see it. Never for work whose result you need back in this session; that is a subagent.
---

# Spawn a tab

`~/.claude/skills/spawn-tab/spawn` opens a named tab in the current Zellij session and starts `claude` in it with a prompt. The new session is Thomas's to take over: it is interactive, it appears in his tab bar, and it is reachable from his phone like any session he starts himself.

```
~/.claude/skills/spawn-tab/spawn [options] NAME [PROMPT] [-- CLAUDE_ARGS...]
echo PROMPT | ~/.claude/skills/spawn-tab/spawn [options] NAME
```

| Option | Does |
| --- | --- |
| `-d DIR` | starts the session in that directory; the default is the current one |
| `-w WORKTREE` | starts it in a new git worktree of that name |
| `-s SESSION` | names the Zellij session; the default is `$ZELLIJ_SESSION_NAME` |
| `--focus` | moves Thomas to the new tab; without it his focus stays where it is |
| `--max N` | refuses when the session already has N tabs; the default is 8 |
| `--dry-run` | prints the command and opens nothing |

It prints the new tab's id. It refuses a tab name that is already open, a directory that does not exist, and a session at its tab limit. Pass a long prompt on stdin.

## A tab is a handoff, not delegation

**Nothing comes back from a spawned tab.** You cannot wait on it and it sends you no result.

- Work whose answer you need to continue: use a subagent.
- Work Thomas wants to watch, steer, or continue later: use a tab.
- Unattended work that ends in a pull request: follow the repository's own rules for it. A tab is not a way around them.

Open a tab when Thomas asks for one. Suggest one when a side task has grown into its own piece of work; do not open it unasked.

## Rules

1. **The brief stands alone.** The new session knows nothing of this conversation. Write the goal, what is already known or ruled out, the files to read, and what done means. Point at files; do not paste them.
2. **Name the tab for the work**, in two or three words. Thomas finds it by that name in the tab bar and on his phone.
3. **Code changes start in a worktree** with `-w` whenever another session may be editing the same checkout. Two sessions in one checkout overwrite each other and share one dev stack. Follow the repository's rules for worktree names and setup.
4. **Respect the tab limit.** Each session holds several hundred megabytes plus its own MCP and language servers. A refusal means ask Thomas which tab to close; never raise `--max` to get past it.
5. **Close only a tab you opened, and only when Thomas says so:** `zellij action close-tab-by-id <id>`.
6. **Tell Thomas the tab's name** and what you asked it to do, in the same reply.

## Looking at a spawned tab

```
zellij action list-tabs
zellij action list-panes -t -c          # which pane is in which tab, and its command
zellij action dump-screen -p terminal_<n>
```

Read its screen when Thomas asks how it is going. Do not type into it.
