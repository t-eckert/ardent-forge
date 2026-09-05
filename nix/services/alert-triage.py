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
PLAYBOOK    = os.environ.get("AT_PLAYBOOK", "/data/ardent-forge/repo/nix/services/alert-triage-playbook.md")

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
# unforeseen. Note what is NOT here: no sudo, no nixos-rebuild switch (which
# needs a password this user does not have anyway), no git merge, no push to
# a default branch.
BASE_TOOLS = [
    "Read", "Grep", "Glob", "Edit", "Write",
    "Bash(journalctl:*)", "Bash(systemctl status:*)", "Bash(systemctl is-active:*)",
    "Bash(systemctl --failed:*)", "Bash(systemctl --user:*)",
    "Bash(curl -s http://127.0.0.1:3100/*)", "Bash(curl -sG http://127.0.0.1:3100/*)",
    "Bash(curl -s http://127.0.0.1:8090/*)",
    "Bash(nixos-rebuild build:*)",
    "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)", "Bash(git show:*)",
    "Bash(git checkout -b:*)", "Bash(git add:*)", "Bash(git commit:*)",
    "Bash(git push origin HEAD:*)",
    "Bash(tail:*)", "Bash(head:*)", "Bash(cat:*)", "Bash(ls:*)", "Bash(stat:*)",
    "Bash(md5sum:*)", "Bash(npx prisma generate:*)", "Bash(date:*)",
]
PR_TOOL = "Bash(gh pr create:*)"
DENY = ["Bash(sudo:*)", "Bash(nixos-rebuild switch:*)", "Bash(git merge:*)",
        "Bash(git push origin main:*)", "Bash(rm -rf:*)"]

def build_prompt(msg, sig, verdict_path, may_pr):
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
- chill-subs: never push, never merge. Its main deploys to production.
- {"You MAY open a PR (gh pr create) if the playbook allows T3 AND nixos-rebuild build passes first." if may_pr else "You may NOT open a PR on this run: the daily PR budget is spent. Diagnose and report instead."}
- Do not restart a unit merely to clear an alert.

When done, write your verdict as JSON to {verdict_path}:
  {{"tier": "T0|T1|T2|T3|T4",
    "real": true|false,
    "summary": "<= 300 chars, what you found and did",
    "actions": ["..."],
    "pr_url": "<url or null>"}}
Write that file even if you conclude nothing should be done."""

def run_claude(msg, sig, may_pr, timeout_s=900):
    vdir = os.path.join(STATE_DIR, "verdicts"); os.makedirs(vdir, exist_ok=True)
    vpath = os.path.join(vdir, f"{int(time.time())}-{re.sub(r'[^a-z0-9]+','-',sig.lower())[:40]}.json")
    tools = BASE_TOOLS + ([PR_TOOL] if may_pr else [])
    cmd = ["claude", "-p", build_prompt(msg, sig, vpath, may_pr),
           "--allowedTools", ",".join(tools),
           "--disallowedTools", ",".join(DENY)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        out = (r.stdout or "")[-2000:]
    except subprocess.TimeoutExpired:
        return {"tier": "T1", "real": None, "summary": f"triage timed out after {timeout_s}s", "pr_url": None}, ""
    verdict = None
    if os.path.exists(vpath):
        try: verdict = json.load(open(vpath))
        except Exception: verdict = None
    if verdict is None:
        verdict = {"tier": "T1", "real": None,
                   "summary": "triage produced no verdict file; treat as diagnose-only", "pr_url": None}
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
        print(f"     verdict: tier={tier} real={verdict.get('real')} pr={pr}")
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
