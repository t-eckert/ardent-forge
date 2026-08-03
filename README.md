# Ardent Forge

Hey — welcome to my workshop.

I've spent a lot of years tuning the way I write code: the tools I reach for, the habits, the little machines that quietly take the boring parts off my plate. Ardent Forge is where a good chunk of that lives now. It's a NixOS config I run on a small server at home, and I can get to it from anywhere over Tailscale. I SSH in for a full coding environment with all of my tools pre-installed and the ability to host long-running Claude Code sessions. When I run a dev server, it gets shared over Tailscale.

It's built for me, so it's full of my particular choices. But you're welcome to poke around. If a piece of it is useful, take it and make your own.

### The box

A few habits keep the machine itself simple, and these are the bits I'd most recommend borrowing:

- **The box is nukable.** Nothing precious lives on it. Repos clone fresh from GitHub, and a rebuild doesn't cost me anything.
- **Secrets stay in 1Password.** Decrypted values never touch the disk — they're resolved right when a task starts, and each repo only gets to see the secrets it's declared.
- **Zellij so I can watch.** Because code work runs in a named session, I can SSH in and watch an agent work in real time. I can also just grab the controls and do my own development.
- **Tailscale is the front door.** The whole thing lives on my tailnet, so there's no auth layer to build and nothing sitting out on the public internet, but I can also open a funnel to particular ports if I need to.
