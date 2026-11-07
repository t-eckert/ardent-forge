#!/usr/bin/env python3
"""Alert triage runner.

Polls the ntfy topic Grafana alerts land on, decides -- mechanically, before any
model is involved -- whether an alert is worth acting on, and only then hands it
to `claude -p`.

The limits here are deliberately not left to the model's judgement. A triage run
that reasons badly can still only do what this file permits: the caps, the
cooldown and the synthetic-alert filter are enforced in code, and the model is
never asked to respect them.
"""
import json, os, re, subprocess, sys, time
from datetime import datetime, timedelta, timezone

NTFY        = os.environ.get("AT_NTFY", "http://127.0.0.1:8090/ardent-forge")
STATE_DIR   = os.environ.get("AT_STATE_DIR",
                             os.path.expanduser("~/.local/state/alert-triage"))
STATE_PATH  = os.path.join(STATE_DIR, "state.json")
PLAYBOOK    = os.environ.get("AT_PLAYBOOK", "alert-triage-playbook.md")
# The agent works in a clone of its own, never in a checkout someone else uses.
# It is reset to origin/main before every run.
CLONE       = os.environ.get("AT_CLONE", os.path.join(STATE_DIR, "ardent-forge"))
REPO_URL    = os.environ.get("AT_REPO_URL", "https://github.com/t-eckert/ardent-forge.git")
BASE_BRANCH = "main"

# Mechanical guardrails.
MAX_RUNS_PER_DAY      = int(os.environ.get("AT_MAX_RUNS", "8"))
MAX_PRS_PER_DAY       = int(os.environ.get("AT_MAX_PRS", "1"))
SIGNATURE_COOLDOWN_H  = int(os.environ.get("AT_COOLDOWN_H", "24"))

def now(): return datetime.now(timezone.utc)
def today(): return now().strftime("%Y-%m-%d")

def load_state():
    try:
        with open(STATE_PATH) as f: return json.load(f)
    except Exception:
        return {"last_time": 0, "seen_ids": [], "signatures": {}, "daily": {}}

def save_state(s):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f: json.dump(s, f, indent=2, sort_keys=True)
    os.replace(tmp, STATE_PATH)

def fetch(since):
    url = f"{NTFY}/json?poll=1&since={since}"
    out = subprocess.run(["curl", "-s", "--max-time", "20", url],
                         capture_output=True, text=True, timeout=40).stdout
    msgs = []
    for line in out.splitlines():
        line = line.strip()
        if not line: continue
        try: m = json.loads(line)
        except Exception: continue
        if m.get("event") == "message": msgs.append(m)
    return msgs

def signature(msg):
    """Stable key for an alert, independent of firing/resolved and counts."""
    title = msg.get("title", "")
    t = re.sub(r"^[^\w\[]*", "", title)
    t = re.sub(r"\[(FIRING|RESOLVED)(:\d+)?\]\s*", "", t)
    return t.strip() or "(untitled)"

def classify(msg):
    """Returns (actionable, reason). Mechanical pre-filter, no model involved."""
    title = msg.get("title", "") or ""
    body  = msg.get("message", "") or ""
    blob  = f"{title}\n{body}"
    # Catches a manually published test notification, but NOT a synthetic
    # Grafana alert: Grafana sends the rule's annotation summary, not the log
    # line that tripped it, so a marker injected into the log never reaches
    # here. Measured -- a fully synthetic reindex alert passed this check
    # untouched. Establishing that a failure is real is therefore part of
    # triage against the source logs, not something this filter can decide.
    if "SYNTHETIC" in blob.upper():
        return False, "synthetic/test notification"
    if "RESOLVED" in title.upper():
        return False, "resolved notice, nothing to fix"
    if "FIRING" not in title.upper():
        return False, "not a firing alert"
    return True, "firing"


# Tools the unattended run may use. Anything absent fails closed, which
# degrades the run to diagnosis rather than letting it reach for something
# unforeseen. Note what is NOT here: no sudo, no nixos-rebuild switch, no git
# checkout, no push and no gh at all. A push to ardent-forge's main deploys the
# box, so the model never pushes: it commits in its clone, and open_pr() below
# pushes only to a triage/* branch, after its own build check. Edit and Write
# reach only the clone.
BASE_TOOLS = [
    "Read", "Grep", "Glob", f"Edit(/{CLONE}/**)", f"Write(/{CLONE}/**)",
    "Bash(journalctl:*)", "Bash(systemctl status:*)", "Bash(systemctl is-active:*)",
    "Bash(systemctl --failed:*)", "Bash(systemctl --user:*)",
    "Bash(curl -s http://127.0.0.1:3100/*)", "Bash(curl -sG http://127.0.0.1:3100/*)",
    "Bash(curl -s http://127.0.0.1:8090/*)",
    "Bash(nixos-rebuild build:*)",
    "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)", "Bash(git show:*)",
    "Bash(git add:*)", "Bash(git commit:*)",
    "Bash(tail:*)", "Bash(head:*)", "Bash(cat:*)", "Bash(ls:*)", "Bash(stat:*)",
    "Bash(md5sum:*)", "Bash(npx prisma generate:*)", "Bash(date:*)",
]
DENY = ["Bash(sudo:*)", "Bash(nixos-rebuild switch:*)", "Bash(git merge:*)",
        "Bash(git push:*)", "Bash(git checkout:*)", "Bash(git switch:*)",
        "Bash(git reset:*)", "Bash(gh:*)", "Bash(rm -rf:*)"]

def git(*args, timeout=120):
    return subprocess.run(["git", "-C", CLONE, *args], capture_output=True,
                          text=True, timeout=timeout)

def prepare_clone(branch):
    """A fresh tree at origin/main on a new triage/* branch, or an error string."""
    if not os.path.isdir(os.path.join(CLONE, ".git")):
        r = subprocess.run(["git", "clone", "-q", REPO_URL, CLONE],
                           capture_output=True, text=True, timeout=300)
        if r.returncode: return f"clone failed: {r.stderr.strip()[:300]}"
    for args in (["fetch", "-q", "--prune", "origin"],
                 ["checkout", "-q", "-B", branch, f"origin/{BASE_BRANCH}"],
                 ["reset", "-q", "--hard", f"origin/{BASE_BRANCH}"],
                 ["clean", "-q", "-fdx"]):
        r = git(*args)
        if r.returncode: return f"git {args[0]} failed: {r.stderr.strip()[:300]}"
    return None

def open_pr(branch, verdict):
    """Push the run's commits to its triage/* branch and open a PR. Enforced
    here, not in the prompt: the branch name is ours, the build must pass, and
    the model never touches the remote. Returns (url, reason)."""
    assert branch.startswith("triage/"), branch
    if verdict.get("tier") != "T3":
        return None, "not a T3 verdict"
    title = (verdict.get("pr_title") or "").strip()
    if not title:
        return None, "verdict has no pr_title"
    ahead = git("rev-list", "--count", f"origin/{BASE_BRANCH}..HEAD").stdout.strip()
    if ahead in ("", "0"):
        return None, "no commits to propose"
    b = subprocess.run(["nixos-rebuild", "build", "--flake", f"{CLONE}/nix#ardent-forge", "--impure"],
                       cwd=CLONE, capture_output=True, text=True, timeout=1800)
    if b.returncode:
        return None, "build failed; no PR opened: " + (b.stderr or b.stdout).strip()[-300:]
    r = git("push", "-q", "origin", f"HEAD:refs/heads/{branch}", timeout=120)
    if r.returncode:
        return None, f"push failed: {r.stderr.strip()[:300]}"
    body = (verdict.get("pr_body") or verdict.get("summary") or "").strip()
    body += "\n\nOpened by alert-triage after `nixos-rebuild build` passed."
    pr = subprocess.run(["gh", "pr", "create", "--base", BASE_BRANCH, "--head", branch,
                         "--title", title, "--body", body],
                        cwd=CLONE, capture_output=True, text=True, timeout=120)
    if pr.returncode:
        return None, f"gh pr create failed: {pr.stderr.strip()[:300]}"
    return pr.stdout.strip().splitlines()[-1], "opened"

def build_prompt(msg, sig, verdict_path, may_pr, branch):
    return f"""You are the unattended alert-triage run on ardent-forge. A Grafana
alert fired and reached ntfy. Triage it.

ALERT
  signature: {sig}
  title:     {msg.get('title','')}
  body:      {msg.get('message','')[:1500]}

Read the playbook first and follow it: {PLAYBOOK}

Rules that are not negotiable:
- Establish the failure is REAL before acting. The alert body carries the rule's
  annotation, not the log line, so a synthetic alert looks identical here. If the
  condition is already false or the source logs say SYNTHETIC, this is T0: say so
  and stop.
- Default to T1 (diagnose only). Act only where the playbook names a tier.
- You cannot push, merge or open PRs, in any repo. Your working directory is a
  fresh clone of ardent-forge on branch {branch}, and Edit and Write reach only
  this clone. Never touch chill-subs' git history; its main deploys to production.
- {"If the playbook allows T3: make the fix here, run nixos-rebuild build, commit it, and set pr_title and pr_body in the verdict. The runner rebuilds, pushes this branch and opens the PR; if its build fails, no PR is opened." if may_pr else "No PR on this run: the daily PR budget is spent. Do not commit; diagnose and report instead."}
- Do not restart a unit merely to clear an alert.

When done, write your verdict as JSON to {verdict_path}:
  {{"tier": "T0|T1|T2|T3|T4",
    "real": true|false,
    "summary": "<= 300 chars, what you found and did",
    "actions": ["..."],
    "pr_title": "<only for T3 with a commit, else null>",
    "pr_body": "<only for T3: what changed and how it was verified, else null>"}}
Write that file even if you conclude nothing should be done."""

def run_claude(msg, sig, may_pr, timeout_s=900):
    vdir = os.path.join(STATE_DIR, "verdicts"); os.makedirs(vdir, exist_ok=True)
    slug = re.sub(r'[^a-z0-9]+','-',sig.lower()).strip('-')[:40] or "alert"
    stamp = int(time.time())
    vpath = os.path.join(vdir, f"{stamp}-{slug}.json")
    branch = f"triage/{slug}-{stamp}"
    err = prepare_clone(branch)
    if err:
        return {"tier": "T1", "real": None, "summary": f"could not prepare the clone ({err}); no triage run", "pr_url": None}, ""
    cmd = ["claude", "-p", build_prompt(msg, sig, vpath, may_pr, branch),
           "--allowedTools", ",".join(BASE_TOOLS),
           "--disallowedTools", ",".join(DENY)]
    try:
        r = subprocess.run(cmd, cwd=CLONE, capture_output=True, text=True, timeout=timeout_s)
        out = (r.stdout or "")[-2000:]
    except subprocess.TimeoutExpired:
        return {"tier": "T1", "real": None, "summary": f"triage timed out after {timeout_s}s", "pr_url": None}, ""
    verdict = None
    if os.path.exists(vpath):
        try: verdict = json.load(open(vpath))
        except Exception: verdict = None
    if verdict is None:
        verdict = {"tier": "T1", "real": None,
                   "summary": "triage produced no verdict file; treat as diagnose-only"}
    verdict["pr_url"] = None
    if may_pr:
        verdict["pr_url"], verdict["pr_note"] = open_pr(branch, verdict)
    return verdict, out

def notify(text, title):
    subprocess.run(["curl", "-s", "--max-time", "15", "-H", f"Title: {title}",
                    "-d", text[:1500], NTFY], capture_output=True, timeout=30)

def main():
    dry = "--dry-run" in sys.argv
    # An off switch that does not depend on the model, the prompt, or the
    # timer: `touch ~/.local/state/alert-triage/PAUSED` and nothing acts.
    pause = os.path.join(STATE_DIR, "PAUSED")
    if os.path.exists(pause):
        print(f"[paused] {pause} exists - not acting on anything")
        return 0
    st = load_state()
    since = st.get("last_time") or "12h"
    msgs = fetch(since)
    seen = set(st.get("seen_ids", []))
    daily = st.get("daily", {}).get(today(), {"runs": 0, "prs": 0})

    fresh = [m for m in msgs if m.get("id") not in seen]
    print(f"[{now().strftime('%H:%M:%S')}] polled since={since}: {len(msgs)} msgs, {len(fresh)} new")

    acted = []
    for m in fresh:
        sig = signature(m)
        ok, why = classify(m)
        if not ok:
            print(f"  SKIP  {sig!r}: {why}")
            seen.add(m["id"]); continue

        rec = st.get("signatures", {}).get(sig, {})
        last = rec.get("last_handled")
        if last:
            age_h = (now() - datetime.fromisoformat(last)).total_seconds() / 3600
            if age_h < SIGNATURE_COOLDOWN_H:
                print(f"  SKIP  {sig!r}: cooldown, handled {age_h:.1f}h ago (<{SIGNATURE_COOLDOWN_H}h)")
                seen.add(m["id"]); continue

        if daily["runs"] >= MAX_RUNS_PER_DAY:
            print(f"  STOP  {sig!r}: daily run cap {MAX_RUNS_PER_DAY} reached")
            break

        print(f"  ACT   {sig!r}: {why}  (pr budget left today: {MAX_PRS_PER_DAY - daily['prs']})")
        acted.append((m, sig))
        seen.add(m["id"])
        daily["runs"] += 1
        # Record the handling that the cooldown above reads. Without this the
        # cooldown silently never triggers: it checks a key nothing writes.
        st.setdefault("signatures", {}).setdefault(sig, {})
        st["signatures"][sig]["last_handled"] = now().isoformat()
        st["signatures"][sig]["handled_count"] = st["signatures"][sig].get("handled_count", 0) + 1

    if not dry:
        st["seen_ids"] = list(seen)[-500:]
        if msgs: st["last_time"] = max(int(m.get("time", 0)) for m in msgs)
        st.setdefault("daily", {})[today()] = daily
        save_state(st)

    print(f"[summary] actionable={len(acted)} runs_today={daily['runs']}/{MAX_RUNS_PER_DAY} "
          f"prs_today={daily['prs']}/{MAX_PRS_PER_DAY} dry_run={dry}")
    if dry:
        for m, sig in acted:
            print(f"  -> would invoke triage for: {sig}")
        return 0

    for m, sig in acted:
        may_pr = daily["prs"] < MAX_PRS_PER_DAY
        print(f"  -> triaging {sig!r} (may_pr={may_pr})")
        verdict, tail = run_claude(m, sig, may_pr)
        tier = verdict.get("tier", "T1")
        pr = verdict.get("pr_url")
        print(f"     verdict: tier={tier} real={verdict.get('real')} pr={pr} ({verdict.get('pr_note', 'no PR budget')})")
        print(f"     {verdict.get('summary','')[:300]}")
        if pr:
            daily["prs"] += 1
            st["signatures"][sig]["last_pr"] = pr
        st["signatures"][sig]["last_tier"] = tier
        notify(f"{verdict.get('summary','(no summary)')}" + (f"\n\nPR: {pr}" if pr else ""),
               f"triage {tier}: {sig}")
        st.setdefault("daily", {})[today()] = daily
        save_state(st)
    return 0

if __name__ == "__main__":
    sys.exit(main())
