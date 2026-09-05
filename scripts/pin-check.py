#!/usr/bin/env python3
"""Report and refresh the pins this config carries outside the flake lock.

Flake inputs have `af-rebuild --update`. These do not: Go module pseudo-versions
for the caddy plugins, and container image digests. They are pinned by hand,
which means they are updated only when someone remembers, and both had drifted
by the better part of a year before anyone looked.

This is deliberately a plain script and not an agent. Resolving a tag to a
digest and rewriting a string is fully determined -- there is no judgement in
it, so a model would add cost and nondeterminism and buy nothing.

    pin-check                 report what is stale
    pin-check --update        rewrite the pins, resolve the plugin hash, build

It never switches: `nixos-rebuild switch` needs a password this cannot supply,
and a passing build is not proof the tsnet nodes still register with control.
Review the diff and switch by hand.
"""
import argparse, json, os, re, subprocess, sys, urllib.request

REPO = "/data/ardent-forge/repo"
CADDY_NIX = "nix/services/caddy.nix"

PINS = [
    {"kind": "gomod", "name": "caddy-tailscale", "gh": "tailscale/caddy-tailscale",
     "branch": "main", "file": CADDY_NIX, "module": "github.com/tailscale/caddy-tailscale"},
    {"kind": "gomod", "name": "caddy-webdav", "gh": "mholt/caddy-webdav",
     "branch": "master", "file": CADDY_NIX, "module": "github.com/mholt/caddy-webdav"},
    {"kind": "oci", "name": "the-weather", "file": "nix/services/the-weather.nix",
     "ref": "ghcr.io/t-eckert/the-weather", "tag": "latest"},
    {"kind": "oci", "name": "ntfy", "file": "nix/services/ntfy.nix",
     "ref": "docker.io/binwiederhier/ntfy", "tag": "latest"},
]

def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)

def read(rel):
    with open(os.path.join(REPO, rel)) as f: return f.read()

def write(rel, s):
    with open(os.path.join(REPO, rel), "w") as f: f.write(s)

# ---------------------------------------------------------------- resolvers --

def gh_head(repo, branch):
    """Latest commit on a branch, as (sha, pseudo-version timestamp)."""
    url = f"https://api.github.com/repos/{repo}/commits/{branch}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "pin-check"})
    with urllib.request.urlopen(req, timeout=25) as r:
        d = json.load(r)
    sha = d["sha"][:12]
    # Go pseudo-versions use the COMMIT date in UTC, not the author date.
    date = d["commit"]["committer"]["date"]           # 2026-08-26T18:03:04Z
    ts = re.sub(r"[-:TZ]", "", date)                  # 20260826180304
    return sha, ts

def oci_digest(ref, tag):
    env = dict(os.environ)
    # skopeo otherwise looks under /run/containers/<uid>, which is root-owned
    # here, and fails on a permission error before reaching the network.
    env.setdefault("REGISTRY_AUTH_FILE",
                   os.path.expanduser("~/.config/containers/auth.json"))
    r = sh(["skopeo", "inspect", f"docker://{ref}:{tag}"], env=env, timeout=60)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout).get("Digest")
    except Exception:
        return None

# ------------------------------------------------------------------- checks --

def current_gomod(pin):
    m = re.search(re.escape(pin["module"]) + r"@v0\.0\.0-(\d{14})-([a-f0-9]{12})",
                  read(pin["file"]))
    return (m.group(2), m.group(1)) if m else (None, None)

def current_oci(pin):
    m = re.search(re.escape(pin["ref"]) + r"@(sha256:[a-f0-9]{64})", read(pin["file"]))
    return m.group(1) if m else None

def survey():
    rows = []
    for pin in PINS:
        if pin["kind"] == "gomod":
            cur_sha, cur_ts = current_gomod(pin)
            try:
                new_sha, new_ts = gh_head(pin["gh"], pin["branch"])
            except Exception as e:
                rows.append((pin, f"{cur_ts} {cur_sha}", f"lookup failed: {e}", None)); continue
            stale = (cur_sha != new_sha)
            rows.append((pin, f"{cur_ts} {cur_sha}", f"{new_ts} {new_sha}",
                         (new_sha, new_ts) if stale else None))
        else:
            cur = current_oci(pin)
            new = oci_digest(pin["ref"], pin["tag"])
            if new is None:
                rows.append((pin, (cur or "?")[:26], "lookup failed", None)); continue
            rows.append((pin, (cur or "unpinned")[:26], new[:26], new if cur != new else None))
    return rows

# ------------------------------------------------------------------ updates --

FAKE = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="

def build(capture=True):
    return sh(["nixos-rebuild", "build", "--flake", f"{REPO}/nix#ardent-forge", "--impure"],
              cwd="/tmp", timeout=3600)

def resolve_plugin_hash():
    """Set the caddy plugin hash to a wrong value, build, read the right one back."""
    s = read(CADDY_NIX)
    cur = re.search(r'hash = "(sha256-[A-Za-z0-9+/=]+)";', s)
    if not cur:
        print("  ! could not find the plugin hash line"); return False
    write(CADDY_NIX, s.replace(cur.group(1), FAKE, 1))
    print("  building to learn the new plugin hash (this compiles caddy)...")
    r = build()
    got = re.search(r"got:\s+(sha256-[A-Za-z0-9+/=]+)", r.stderr or "")
    if not got:
        # Restore rather than leave a deliberately wrong hash behind.
        write(CADDY_NIX, read(CADDY_NIX).replace(FAKE, cur.group(1), 1))
        print("  ! build did not report a replacement hash; restored the original")
        print((r.stderr or "")[-800:])
        return False
    write(CADDY_NIX, read(CADDY_NIX).replace(FAKE, got.group(1), 1))
    print(f"  plugin hash -> {got.group(1)}")
    return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", help="rewrite stale pins and build")
    args = ap.parse_args()

    rows = survey()
    print(f"{'PIN':18} {'CURRENT':30} {'UPSTREAM':30} STALE")
    stale = []
    for pin, cur, new, delta in rows:
        print(f"{pin['name']:18} {cur:30} {new:30} {'yes' if delta else 'no'}")
        if delta: stale.append((pin, delta))

    if not stale:
        print("\nEverything is current."); return 0
    if not args.update:
        print(f"\n{len(stale)} stale. Re-run with --update to rewrite and build."); return 0

    touched_plugins = False
    for pin, delta in stale:
        s = read(pin["file"])
        if pin["kind"] == "gomod":
            new_sha, new_ts = delta
            s = re.sub(re.escape(pin["module"]) + r"@v0\.0\.0-\d{14}-[a-f0-9]{12}",
                       f"{pin['module']}@v0.0.0-{new_ts}-{new_sha}", s, count=1)
            touched_plugins = True
        else:
            s = re.sub(re.escape(pin["ref"]) + r"@sha256:[a-f0-9]{64}",
                       f"{pin['ref']}@{delta}", s, count=1)
        write(pin["file"], s)
        print(f"  updated {pin['name']} in {pin['file']}")

    if touched_plugins and not resolve_plugin_hash():
        return 1

    print("  verifying the whole thing builds...")
    r = build()
    if r.returncode != 0:
        print("  ! build FAILED after updating pins:")
        print((r.stderr or "")[-1500:])
        return 1
    print("  build OK:", (r.stdout or "").strip().splitlines()[-1] if r.stdout else "?")
    print("\nReview `git diff`, then switch by hand. A passing build does not prove")
    print("the tsnet nodes still register -- only activation does.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
