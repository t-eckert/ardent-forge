---
name: open-split
description: Open one pane beside this session's own Zellij pane, in the same tab, to show Thomas something while the conversation carries on - a running log or command output, a shell with a command typed and waiting for him to run, or neovim open on a file at a line. A split when this session is alone in its tab, a floating pane when it is not. Use when a long-running command's output is worth watching, when Thomas has to run a command himself (an interactive login, sudo, anything you may not run), or when he should read or edit a specific file. Also use when Thomas says "open a split", "show me that in a split", "put the log beside this", or "open that file for me".
---

# Open a split

`~/.claude/skills/open-split/split` opens one pane beside this session's pane, in the same tab. Focus stays where Thomas has it.

```
split log  [options] -- COMMAND [ARGS...]   run it now and leave the output up
split cmd  [options] 'COMMAND LINE'         a shell with the line typed, not run
split edit [options] FILE[:LINE]            neovim on the file
split close                                 close the split this script opened
```

| Option | Does |
| --- | --- |
| `--down` | opens below; the default is to the right |
| `--float` | opens a floating pane over the tab instead of a split |
| `-d DIR` | working directory of the split; the default is the current one |
| `--replace` | closes the split this script opened in this tab, then opens the new one |
| `--focus` | moves focus into the split |
| `--dry-run` | prints what would run and opens nothing |

It prints the new pane's id, such as `terminal_24`.

## The three uses

- **`log`** runs a command at once and keeps its output on screen: a `tail -f`, a test watcher, a build. A single argument is run through `sh -c`, so a pipeline goes in one quoted string. Read what it shows with `zellij action dump-screen -p <pane id>`.
- **`cmd`** opens Thomas's shell with one line typed at the prompt and not run. Use it for anything he has to run himself. The line must be a single line; he can edit it before pressing Enter.
- **`edit`** opens neovim on a file, at a line when given `FILE:LINE`. Use it when he should read or change something specific, not as a way to show a diff you could describe.

## Rules

1. **A split only when this session's pane is alone in its tab.** The script refuses a split when any other tiled pane is there. Pass `--float` then: a floating pane sits over the tab and moves nothing. Never close or rearrange a pane to make room.
2. **One pane at a time, split or floating.** To show something else, pass `--replace`, which closes only the pane this script opened. Close it with `split close` when it has served its purpose. A floating pane covers the conversation, so close it sooner.
3. **Never run through `cmd` what you could not run yourself.** `cmd` is for Thomas's hands. Do not follow it with `write-chars` or anything else that presses Enter for him.
4. **Leave focus alone** unless he asked to be put in the split. He may be typing, and keystrokes landing in a shell or an editor do damage.
5. **Say what you opened** and why, in the same reply, in one line.
6. **Do not open one unasked for something short.** Output that fits in a reply belongs in the reply.

## Where the split lands

The script splits the pane named by `ZELLIJ_PANE_ID`. In a session started from the agents view, that is the pane the agents view runs in, which may be showing a different session when the split opens. Open a split there only in reply to something Thomas has just said.
