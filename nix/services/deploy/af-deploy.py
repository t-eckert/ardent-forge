#!/usr/bin/env python3
"""Deploy this box from the commit at origin/main.

Run as root by af-rebuild.service, on a timer and on demand (`af deploy`).
The deploy builds exactly what a commit pins and never updates inputs; moving
a pin is a change pushed like any other.

A deploy happens when origin/main differs from the running system's commit,
or when /etc/ardent-forge/locals.json has changed since the last deploy.
After switching, the critical checks decide what happens next:

  - tailscaled and sshd active, Tailscale online, the repo reachable on
    GitHub. Each is a way back into the box or the way the next fix
    arrives, so if any fails for the whole health window, the box switches
    back to the system it was running.
  - Units that fail after the switch, and were not failing before it, are
    reported but kept: rolling back would undo every unrelated change too.

A commit that fails is remembered and not retried until main moves again
(`af deploy --retry` forces it). Nothing here reboots, and a failed system is
never staged for the next boot.
"""
import argparse, hashlib, json, os, subprocess, sys, time
from datetime import datetime, timezone

REPO_URL = os.environ["AF_REPO_URL"]
BRANCH   = os.environ.get("AF_BRANCH", "main")
HOST     = os.environ.get("AF_HOST", "ardent-forge")
SRC      = os.environ.get("AF_SRC", "/var/lib/af-rebuild/src")
STATE    = os.environ.get("AF_STATE", "/var/lib/af-rebuild/state.json")
LOCALS   = os.environ.get("AF_LOCALS", "/etc/ardent-forge/locals.json")
NTFY     = os.environ.get("AF_NTFY", "")
DRILL    = os.environ.get("AF_DRILL") == "1"
HEALTH_WINDOW_S = int(os.environ.get("AF_HEALTH_WINDOW", "60"))
PROFILE  = "/nix/var/nix/profiles/system"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run(cmd, timeout=None, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)


def log(msg):
    print(msg, flush=True)


def tail(text, n=15):
    return "\n".join((text or "").strip().splitlines()[-n:])


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f, indent=2, sort_keys=True)
    os.chmod(tmp, 0o644)
    os.replace(tmp, STATE)


def remote_rev():
    try:
        r = run(["git", "ls-remote", REPO_URL, f"refs/heads/{BRANCH}"], timeout=60)
    except subprocess.TimeoutExpired:
        return None
    if r.returncode or not r.stdout.strip():
        return None
    return r.stdout.split()[0]


def system_rev(path):
    r = run([f"{path}/sw/bin/nixos-version", "--configuration-revision"])
    return r.stdout.strip() if r.returncode == 0 else ""


def locals_hash():
    try:
        with open(LOCALS, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except FileNotFoundError:
        return None


def failed_units():
    r = run(["systemctl", "list-units", "--failed", "--plain", "--no-legend", "--no-pager"])
    return {line.split()[0] for line in r.stdout.splitlines() if line.strip()}


def critical_problems():
    problems = []
    for unit in ("tailscaled", "sshd"):
        if run(["systemctl", "is-active", "--quiet", unit]).returncode:
            problems.append(f"{unit} is not active")
    try:
        ts = json.loads(run(["tailscale", "status", "--json"], timeout=20).stdout)
        if ts.get("BackendState") != "Running" or not (ts.get("Self") or {}).get("Online"):
            problems.append(f"Tailscale is not online (state {ts.get('BackendState')})")
    except Exception:
        problems.append("tailscale status failed")
    if remote_rev() is None:
        problems.append("the repo on GitHub is unreachable")
    if DRILL:
        problems.append("drill: critical check forced to fail")
    return problems


def wait_healthy():
    """Critical problems still present after the health window, or []."""
    deadline = time.time() + HEALTH_WINDOW_S
    while True:
        problems = critical_problems()
        if not problems or time.time() >= deadline:
            return problems
        time.sleep(5)


def reboot_pending():
    return any(os.path.realpath(f"/run/booted-system/{p}") != os.path.realpath(f"/run/current-system/{p}")
               for p in ("kernel", "initrd", "kernel-modules"))


def switch_to(path):
    """Make `path` the system profile and activate it. Output goes to the journal."""
    r = run(["nix-env", "-p", PROFILE, "--set", path])
    if r.returncode:
        log(r.stderr)
        return r.returncode
    return subprocess.run([f"{path}/bin/switch-to-configuration", "switch"]).returncode


def commit_url(rev):
    base = REPO_URL.removesuffix(".git")
    return f"{base}/commit/{rev}" if base.startswith("https://github.com/") else ""


def notify(title, message, priority="default", rev=None, tags=None):
    if not NTFY:
        return
    headers = ["-H", f"Title: {title}", "-H", f"Priority: {priority}"]
    if rev and commit_url(rev):
        headers += ["-H", f"Click: {commit_url(rev)}"]
    if tags:
        headers += ["-H", f"Tags: {tags}"]
    try:
        run(["curl", "-s", "--max-time", "15", *headers, "-d", message[:3000], NTFY], timeout=30)
    except subprocess.TimeoutExpired:
        log("ntfy did not answer; notification dropped")


def fetch_source():
    if not os.path.isdir(os.path.join(SRC, ".git")):
        r = run(["git", "clone", "-q", "--no-checkout", REPO_URL, SRC], timeout=600)
    else:
        r = run(["git", "-C", SRC, "fetch", "-q", "--prune", "origin"], timeout=600)
    return None if r.returncode == 0 else tail(r.stderr, 5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--retry", action="store_true", help="deploy a commit that failed before")
    ap.add_argument("--force", action="store_true", help="deploy even if already up to date")
    args = ap.parse_args()

    st = load_state()
    st["checked_at"] = now()
    rev = remote_rev()
    if rev is None:
        log(f"cannot read {BRANCH} from {REPO_URL}; trying again next time")
        st["origin_error"] = now()
        save_state(st)
        return 0
    st["origin"] = rev
    st.pop("origin_error", None)

    current = os.path.realpath("/run/current-system")
    current_rev = system_rev(current)
    lhash = locals_hash()
    # The first run after this service appears has no recorded locals hash;
    # adopt the current one rather than redeploying the running commit.
    if current_rev == rev and st.get("locals_hash") in (None, lhash) and not args.force:
        st.update(deployed=rev, system=current, locals_hash=lhash, reboot_pending=reboot_pending())
        save_state(st)
        log(f"up to date at {rev[:7]}")
        return 0

    key = f"{rev}:{lhash}"
    if st.get("failed") == key and not (args.retry or args.force):
        save_state(st)
        log(f"{rev[:7]} failed before; waiting for {BRANCH} to move (af deploy --retry forces it)")
        return 0

    err = fetch_source()
    if err:
        log(f"fetch failed: {err}")
        save_state(st)
        return 1
    subject = run(["git", "-C", SRC, "log", "-1", "--format=%s", rev]).stdout.strip() or "(no subject)"
    short = rev[:7]
    reason = "new commit" if current_rev != rev else ("locals.json changed" if st.get("locals_hash") != lhash else "forced")
    log(f"deploying {short} {subject} ({reason}; running {current_rev[:7] or 'unknown'})")
    started = time.time()
    st["last"] = {"rev": rev, "at": now(), "result": "running", "subject": subject}
    save_state(st)

    flake = f"git+file://{SRC}?rev={rev}&dir=nix#nixosConfigurations.{HOST}.config.system.build.toplevel"
    build = run(["nix", "build", "--no-link", "--print-out-paths", "--impure", flake], timeout=3 * 3600)
    if build.returncode:
        detail = tail(build.stderr)
        log(detail)
        st["failed"] = key
        st["last"] = {"rev": rev, "at": now(), "result": "build-failed", "subject": subject, "detail": detail}
        save_state(st)
        notify(f"Deploy failed: {short}", f"{subject}\n\nThe build failed; nothing changed on the box.\n\n{detail}",
               "high", rev, "x")
        return 1
    new = build.stdout.strip().splitlines()[-1]
    log(f"built {new}")

    before = failed_units()
    code = switch_to(new)
    log(f"switch-to-configuration exited {code}")
    problems = wait_healthy()
    if problems:
        log("critical checks failed: " + "; ".join(problems) + f"; switching back to {current}")
        switch_to(current)
        still = wait_healthy() if not DRILL else [p for p in critical_problems() if not p.startswith("drill")]
        st["failed"] = key
        st["last"] = {"rev": rev, "at": now(), "result": "rolled-back", "subject": subject,
                      "detail": "; ".join(problems), "after_rollback": "; ".join(still)}
        save_state(st)
        msg = f"{subject}\n\nCritical checks failed after switching:\n" + "\n".join(f"- {p}" for p in problems)
        msg += f"\n\nSwitched back to {current_rev[:7] or 'the previous system'}."
        if still:
            msg += "\n\nSTILL FAILING after the rollback:\n" + "\n".join(f"- {p}" for p in still)
        notify(f"Rolled back: {short}", msg, "urgent" if still else "high", rev, "rotating_light")
        return 1

    newly_failed = sorted(failed_units() - before)
    reboot = reboot_pending()
    took = int(time.time() - started)
    st.update(deployed=rev, deployed_at=now(), system=new, locals_hash=lhash, reboot_pending=reboot)
    st.pop("failed", None)
    st["last"] = {"rev": rev, "at": now(), "subject": subject, "took_s": took,
                  "result": "deployed-with-failures" if newly_failed else "deployed",
                  "detail": ", ".join(newly_failed)}
    if newly_failed:
        notify(f"Deployed {short}, units failing", f"{subject}\n\nNewly failing: {', '.join(newly_failed)}\n\nSee `af log`.",
               "default", rev, "warning")
    else:
        notify(f"Deployed {short}", f"{subject}\n\nTook {took}s.", "low", rev, "white_check_mark")
    if reboot and st.get("reboot_notified") != new:
        notify("Reboot pending", "The booted kernel differs from the deployed one. Reboot when convenient.",
               "default", rev, "arrows_counterclockwise")
        st["reboot_notified"] = new
    save_state(st)
    log(f"deployed {short} in {took}s" + (f"; newly failing: {', '.join(newly_failed)}" if newly_failed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
