# implementer

The Forge's coding agent. A ticket delegated to it in Linear becomes a pull request, coded by a Claude Code session in a fenced rootless Podman container. The design is in [`docs/design.md`](docs/design.md).

It is not deployed yet: nothing in `nix/flake.nix` imports `nix/package.nix` or `nix/module.nix`. See "Packaging and deploys" in the design for what has to change first.

## Develop

Needs Node 22.19 or later.

```sh
cd implementer
npm ci
npm test
npm run typecheck
npm run build
node dist/cli.js run implementer --state-dir ./state   # Ctrl-C drains and exits
node dist/cli.js run gateway --state-dir ./state       # takes webhooks on 127.0.0.1:7410
```

The Podman tests run where a session image tagged `localhost/implementer-session:latest` exists, and are skipped otherwise.
