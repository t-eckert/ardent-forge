# nix/services/memory-limits.nix
{ ... }:

# Memory headroom for a 15.4 GiB box that concurrently runs several Claude Code
# sessions (each spawning rust-analyzer / tsserver / pyright / playwright-mcp),
# the Chill Subs + Galley dev suite, Postgres, Grafana and Alloy.
#
# Why this exists: as of 2026-07-28 there were no memory limits anywhere —
# user.slice had MemoryHigh=infinity / MemoryMax=infinity — so every shortage
# became a *global* OOM kill:
#
#   oom-kill:constraint=CONSTRAINT_NONE,...,global_oom
#   Out of memory: Killed process 2343152 (next-router-wor) oom_score_adj:200
#
# With no cgroup limit involved, the kernel picks a victim by score across the
# whole machine. On Jul 28 that meant killing cs-galley-suite's Next.js router
# worker twice, rather than the 4.2 GiB rust-analyzer that actually caused the
# shortage. Three layers below, cheapest first:
#
#   1. zram         — compressed swap in RAM, used before the NVMe partition
#   2. MemoryHigh   — throttle + reclaim (never kills) once user work passes a ceiling
#   3. systemd-oomd — PSI-based kill, only if pressure stays high despite (2)
{
  # ── 1. Compressed swap ─────────────────────────────────────────────────────
  # There was no zram at all: swap was a single 7.5G NVMe partition at priority
  # -2, which filled to its last 8 KiB on Jul 28. Once swap is full the kernel
  # cannot page anything back in, so a process can sit resident-but-stalled with
  # no OOM kill to signal it.
  #
  # JS and Rust heaps compress well (~3:1 with zstd), so a device sized at 50% of
  # RAM typically costs ~2.5 GiB of real memory to hold ~7.7 GiB of pages.
  # Priority 100 puts it well above the NVMe partition, so zram absorbs first and
  # the disk becomes overflow rather than the primary swap.
  zramSwap = {
    enable = true;
    algorithm = "zstd";
    memoryPercent = 50;
    priority = 100;
  };

  # ── 2. Ceiling on user work ────────────────────────────────────────────────
  # `user-.slice` is the per-user template, so this covers BOTH interactive login
  # scopes (session-N.scope — where zellij, Claude Code and the language servers
  # actually live) and user services under user@1000.service (cs-galley-suite).
  # System services — Postgres, Grafana, Alloy, Caddy, thomaseckert-dev — sit in
  # system.slice and are deliberately left uncapped here.
  #
  # MemoryHigh is a *throttle*, not a limit: crossing it forces reclaim and slows
  # the cgroup, it does not kill. That is the desired behaviour — a sluggish
  # rust-analyzer beats an OOM-killed dev suite.
  #
  # Sized from measurements taken 2026-07-28, not guessed:
  #
  #   user-1000.slice   8.88 GiB current   14.03 GiB peak   <- the peak is what OOM'd
  #   system.slice      1.25 GiB current
  #   MemTotal         15.40 GiB
  #
  # So the ceiling has to sit above normal working set (~9 GiB) but below the
  # ~14 GiB peak that exhausted the box. 11G does that: day-to-day work is
  # untouched, and reclaim starts well before the machine runs out. Note that a
  # ceiling at 9G would have throttled continuously at the observed idle load —
  # worth re-checking these numbers before changing it.
  #
  # Observe with:
  #   cat /sys/fs/cgroup/user.slice/user-1000.slice/memory.current
  #   cat /sys/fs/cgroup/user.slice/user-1000.slice/memory.peak
  #   cat /sys/fs/cgroup/user.slice/user-1000.slice/memory.events   # `high` counter
  #
  # A climbing `high` counter means the throttle is doing its job. A `high`
  # counter that climbs constantly during ordinary work means it is set too low.
  systemd.slices."user-".sliceConfig = {
    MemoryHigh = "11G";
  };

  # ── 3. Pressure-based backstop ─────────────────────────────────────────────
  # systemd-oomd was already enabled and running, but had taken zero actions in
  # 14 days: /etc/systemd/oomd.conf was empty and ManagedOOMMemoryPressure was
  # left at "auto", which means "off unless a slice opts in" — and nothing opted
  # in. enableUserSlices makes the user slices opt in, so oomd can act on
  # sustained PSI pressure before the kernel's global OOM killer has to guess.
  #
  # Deliberately NOT enabled for system.slice or the root slice: oomd killing
  # Postgres or Caddy under pressure would be worse than the disease.
  systemd.oomd = {
    enable = true;
    enableUserSlices = true;
    enableSystemSlice = false;
    enableRootSlice = false;
  };
}
