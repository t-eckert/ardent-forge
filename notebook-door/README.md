# The Notebook door

The Notebook's MCP endpoint, served on the Forge at `nb.<tailnet>/mcp`: the one careful way other agents read and write the Notebook. It is the first piece of the Notebook Assistant's MCP door, and stet is its first caller. `nix/services/notebook-door.nix` runs it.

Plain TypeScript on Node 24, run directly with no build step and no runtime dependencies.

```sh
npm install      # only TypeScript and Node's types, for the typecheck
npm test
npm run typecheck
```

## Operations

`list`, `search` and `read`; `create_note`, which fails if the note exists; and `update_note`, which carries the hash `read` returned and is refused if the note changed since. No delete, no move. A read-only caller is not offered the two write tools at all.

## Grants and the deny list

Each caller authenticates with a bearer token of its own. `/etc/ardent-forge/notebook-door.json` maps the name of the environment variable holding each token to that caller's grant: the folders (ending in `/`) and notes it may read, the narrower set it may write, and whether it may file new notes in the Notebook root. `config.example.json` is the template. The real file names notes, and this repo is public, so it is placed by hand:

```sh
sudo install -m 0644 notebook-door.json /etc/ardent-forge/notebook-door.json
```

The tokens are resolved by `op run` from `nix/services/notebook-door.env`. A grant whose token is unset has no caller.

The deny list wins over every grant. It names notes by path, and any note with `private: true` in its frontmatter is denied too. A denied note is never named: not by `read`, `list` or `search`.

## Writes

Before writing, the door checks what it can mechanically: a new note has frontmatter with `type`, `field` and `created`, and the caller's `author:`; there is no emoji; a folder of dated notes gets a dated name; research notes have a `## Reference` section; and nothing loads a URL when viewed (external image embeds, raw HTML, `data:` and `javascript:` links).

Each write then takes a syncshot pause lease, fetches, and is refused if GitHub has a newer version of that note than the checkout (the caller retries once syncshot has caught up). It checks the hash or that the note is new, writes to a file outside the tree and renames it in, and commits that one path with `syncshot.py commit --author`, so `git blame` credits the caller with exactly its lines. syncshot pushes it on its next tick.
