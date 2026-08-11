# nix/services/fuzz-isolation.nix
{
  config,
  lib,
  pkgs,
  ...
}:

# An opt-in blast shield for adversarial testing against the Chill Subs +
# Galley dev suite.
#
# Why this exists: on 2026-08-10, before letting an agent fuzz the suite, an
# audit of dev-suite/env showed the databases were local (Mongo on :27017,
# Galley Postgres on :7432, Typesense on :8108) but several sinks were not:
#
#   admin.env / editor.env   S3_ACCESS_KEY=AKIA…  with NO S3_ENDPOINT and
#                            S3_BUCKET_NAME=chillsubs — i.e. the real AWS
#                            *production* bucket. chillest-subs and the Galley
#                            backend both set S3_ENDPOINT to local MinIO; admin
#                            and editor did not.
#   admin.env / editor.env   SENDGRID_API_KEY=SG.… — Mailgun is stubbed to
#                            localhost:8024, SendGrid is not. Live key, real mail.
#   chillest-subs.env        UPSTASH_REDIS_REST_URL, TURSO_DATABASE_URL —
#                            live hosted stores, both writable.
#
# dev-suite/env/*.env.local overlays now neuter those credentials, and that is
# the first line of defence. But an overlay only removes the *configured*
# capability: a hardcoded fallback, a vendored SDK default, or a URL built from
# CLIENT_ORIGIN (still https://www.chillsubs.com) can still egress. This module
# is the second line — it removes the *capability itself*, in the kernel, where
# no amount of application code can talk its way past it.
#
# Deliberately scoped, not global. A box-wide egress block would also cut
# Tailscale, nix substituters, and the Claude Code API session driving the fuzz
# run. So the block applies to one slice, and only what you explicitly launch
# into that slice is affected.
#
# Enable with `ardentForge.fuzzIsolation.enable = true;` then rebuild. Leaving
# it false is the normal state and costs nothing.

let
  cfg = config.ardentForge.fuzzIsolation;

  # Everything the suite legitimately needs, and nothing else.
  #
  #   localhost      Next dev servers, the mailgun stub, and every rootless
  #                  podman port-forward (Mongo, Postgres, Typesense) — those
  #                  bind on 127.0.0.1 via rootlessport, so loopback covers them.
  #   100.64.0.0/10  Tailscale CGNAT range. Covers the local MinIO — verified
  #                  2026-08-10: ardent-forge.feist-gondola.ts.net resolves to
  #                  100.80.227.62 — and MagicDNS at 100.100.100.100.
  #   fd7a:115c:…/48 Tailscale's IPv6 ULA. /etc/resolv.conf lists
  #                  fd7a:115c:a1e0::53 as a nameserver alongside the v4 one, so
  #                  without this the v6 resolver path is silently blocked.
  #   10.88/10.89    podman's default rootless CNI networks, for container-to-
  #                  container traffic that does not go via loopback.
  #   192.168.0.0/16 the LAN (this box is 192.168.2.22).
  #   link-local     DHCP/IPv6 housekeeping; harmless and avoids odd stalls.
  #
  # DNS deliberately fails closed. configuration.nix sets
  # networking.nameservers = [ "1.1.1.1" "8.8.8.8" ], and those are NOT allowed
  # here. In normal operation it does not matter: resolvconf hands DNS to
  # MagicDNS at 100.100.100.100, which is inside the allowed range. But if
  # Tailscale is down and the resolver falls back to the public servers,
  # resolution inside this slice stops working entirely rather than quietly
  # regaining a route off-box. A fuzz run that cannot resolve is the safe
  # failure; one that can reach 8.8.8.8 is not.
  allowedDestinations = [
    "localhost"
    "link-local"
    "100.64.0.0/10"
    "fd7a:115c:a1e0::/48"
    "10.88.0.0/16"
    "10.89.0.0/16"
    "192.168.0.0/16"
  ];

  # ── Launching the dev suite's apps into the slice ──────────────────────────
  #
  # The gap this closes, measured 2026-08-10: IPAddressDeny is silently ignored
  # in systemd *user* units. A user unit carrying IPAddressDeny=any reached
  # s3.amazonaws.com (HTTP 307) exactly as freely as an unrestricted shell. The
  # dev suite runs as cs-galley-suite.service under the user manager, so the
  # filter never applied to the processes that actually hold the credentials.
  #
  # Only the three Next.js apps need to move. The podman containers (Mongo,
  # Postgres, Typesense, MinIO) stay in the user session: they are local-only,
  # hold no production credentials, and rootless podman depends on the user
  # session's XDG_RUNTIME_DIR and setuid newuidmap, which a system unit does not
  # have.
  #
  # Why a locked-down wrapper instead of `NOPASSWD: systemd-run`: passwordless
  # sudo to systemd-run is root-equivalent — it can run anything as root — and
  # sudoers argument matching is too weak to constrain it. This script takes one
  # argument, matches it against a fixed case statement, and hardcodes
  # everything else. There is no path from its arguments to an arbitrary
  # command, so granting NOPASSWD on *this* is not a privilege escalation.
  suiteDir = cfg.suiteDir;
  csRoot = cfg.csRoot;

  fuzzApp = pkgs.writeShellScriptBin "fuzz-app" ''
    set -euo pipefail

    app="''${1:-}"
    action="''${2:-start}"
    unit="fuzz-app-$app"

    case "$app" in
      admin|editor|chillest-subs) : ;;
      *)
        echo "usage: fuzz-app {admin|editor|chillest-subs} [start|stop|status]" >&2
        exit 2
        ;;
    esac

    case "$action" in
      stop)   exec ${pkgs.systemd}/bin/systemctl stop "$unit.service" ;;
      status) exec ${pkgs.systemd}/bin/systemctl status "$unit.service" --no-pager ;;
      start)  : ;;
      *) echo "unknown action: $action" >&2; exit 2 ;;
    esac

    # Everything below is fixed by this script, never taken from argv.
    case "$app" in
      admin)
        dir=${csRoot}/chill-subs/admin
        cmd="yarn dev -p 8030 -H 0.0.0.0"
        ;;
      editor)
        dir=${csRoot}/chill-subs/editor
        cmd="yarn dev -p 8010 -H 0.0.0.0"
        ;;
      chillest-subs)
        dir=${csRoot}/chillest-subs
        cmd="pnpm dev --turbopack -p 8000 -H 0.0.0.0"
        ;;
    esac

    exec ${pkgs.systemd}/bin/systemd-run \
      --unit="$unit" \
      --slice=fuzz.slice \
      --uid=${toString cfg.uid} --gid=${toString cfg.gid} \
      --working-directory="$dir" \
      --setenv=HOME=${cfg.home} \
      --setenv=SUITE_ENV_DIR=${suiteDir}/env \
      --setenv=FUZZ_ISOLATED=1 \
      --setenv=PRISMA_QUERY_ENGINE_LIBRARY=${pkgs.prisma-engines_6}/lib/libquery_engine.node \
      --setenv=PRISMA_QUERY_ENGINE_BINARY=${pkgs.prisma-engines_6}/bin/query-engine \
      --setenv=PRISMA_SCHEMA_ENGINE_BINARY=${pkgs.prisma-engines_6}/bin/schema-engine \
      --setenv=PRISMA_FMT_BINARY=${pkgs.prisma-engines_6}/bin/prisma-fmt \
      --setenv=PATH=/run/wrappers/bin:/etc/profiles/per-user/${cfg.user}/bin:/run/current-system/sw/bin:/usr/bin:/bin \
      --collect \
      -- ${suiteDir}/run-with-env "$app" -- $cmd
  '';

  # Drop a shell (or any command) into the isolated slice.
  #
  # Needs root to create the transient unit — systemd attaches the eBPF filter,
  # so an unprivileged process cannot place itself under a policy it could then
  # escape. The --uid hands the shell straight back to the normal user, so file
  # ownership in the workspace is unchanged.
  fuzzShell = pkgs.writeShellScriptBin "fuzz-shell" ''
    set -euo pipefail
    if [ ! -e /sys/fs/cgroup/fuzz.slice ] && ! systemctl cat fuzz.slice >/dev/null 2>&1; then
      echo "fuzz.slice is not defined — is ardentForge.fuzzIsolation.enable set?" >&2
      exit 1
    fi
    exec sudo systemd-run \
      --slice=fuzz.slice \
      --uid="''${SUDO_UID:-$(id -u)}" \
      --gid="''${SUDO_GID:-$(id -g)}" \
      --same-dir --pty --quiet --collect \
      --setenv=FUZZ_ISOLATED=1 \
      -- "''${@:-${pkgs.bashInteractive}/bin/bash}"
  '';

  # Prove the shield is real rather than trusting that it is.
  #
  # Inside the slice: loopback and the tailnet must work, and the four sinks
  # that could touch production must fail. Outside: everything works. If the
  # "must fail" probes succeed, the slice is not filtering and you should not
  # run a fuzz session.
  fuzzVerify = pkgs.writeShellScriptBin "fuzz-verify" ''
    set -uo pipefail
    curl=${pkgs.curl}/bin/curl
    probe() { # name url expect(ok|blocked)
      code=$($curl -s -o /dev/null -w '%{http_code}' -m 6 "$2" 2>/dev/null) || code="000"
      if [ "$3" = "ok" ]; then
        [ "$code" != "000" ] && echo "  PASS  $1 reachable ($code)" || { echo "  FAIL  $1 unreachable — suite would break"; rc=1; }
      else
        [ "$code" = "000" ] && echo "  PASS  $1 BLOCKED" || { echo "  FAIL  $1 REACHABLE ($code) — production is exposed"; rc=1; }
      fi
    }
    rc=0
    if [ "''${FUZZ_ISOLATED:-0}" = "1" ]; then
      echo "Running INSIDE fuzz.slice — expecting production sinks to be blocked."
      expect=blocked
    else
      echo "Running OUTSIDE fuzz.slice — expecting normal egress."
      echo "(run 'fuzz-shell fuzz-verify' to test the isolated side)"
      expect=ok
    fi
    echo "-- must stay reachable --"
    probe "loopback  (chillest-subs :8000)" "http://localhost:8000/" ok
    echo "-- production sinks --"
    probe "AWS S3        " "https://s3.amazonaws.com"      $expect
    probe "SendGrid      " "https://api.sendgrid.com"      $expect
    probe "Upstash Redis " "https://vocal-trout-36239.upstash.io" $expect
    probe "chillsubs.com " "https://www.chillsubs.com"     $expect
    exit $rc
  '';
in
{
  options.ardentForge.fuzzIsolation = {
    enable = lib.mkEnableOption ''
      a network-isolated systemd slice (fuzz.slice) for adversarial testing.
      Processes launched into it via `fuzz-shell` or `fuzz-app` can reach
      loopback, the tailnet, podman networks and the LAN — and nothing else.
      Enforced by systemd's eBPF address filter, so application code cannot
      bypass it
    '';

    allowClerkAuth = lib.mkEnableOption ''
      egress from fuzz.slice to the Clerk auth IPs in clerkAllowIPs. OFF by
      default. Needed only to test authenticated flows: the editor validates a
      Clerk session against the dev instance, and the slice otherwise denies
      that. Scoped to Clerk's exact addresses — verified 2026-08-10 to be
      disjoint from every resolved Chill Subs IP (216.150.x for the app, and
      104.26/172.67 for search.chillsubs.com), so this does NOT open the
      production API or search. The S3, SendGrid, Upstash and Turso sinks stay
      blocked regardless. Turn back off after the auth-requiring test
    '';
    clerkAllowIPs = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      # Resolved 2026-08-10 for on-elk-6.clerk.accounts.dev + api.clerk.com.
      # Cloudflare-fronted, so these rotate. Refresh with:
      #   getent ahostsv4 on-elk-6.clerk.accounts.dev api.clerk.com
      #   getent ahostsv6 on-elk-6.clerk.accounts.dev api.clerk.com
      # and re-check they stay disjoint from the chillsubs hosts before trusting.
      default = [
        "104.18.34.146"
        "172.64.153.110"
        "104.18.37.202"
        "172.64.150.54"
        "2606:4700:4408::ac40:996e"
        "2a06:98c1:3100::6812:2292"
        "2606:4700:4405::6812:25ca"
        "2606:4700:440d::ac40:9636"
      ];
      description = "Exact Clerk auth IPs allowed out of the slice when allowClerkAuth is on.";
    };

    user = lib.mkOption {
      type = lib.types.str;
      default = "thomaseckert";
      description = "User the isolated apps run as.";
    };
    uid = lib.mkOption {
      type = lib.types.int;
      default = 1000;
      description = "Numeric uid for --uid on the transient unit.";
    };
    gid = lib.mkOption {
      type = lib.types.int;
      default = 100;
      description = "Numeric gid (users) for --gid on the transient unit.";
    };
    home = lib.mkOption {
      type = lib.types.str;
      default = "/home/thomaseckert";
      description = "HOME for the isolated apps — yarn/pnpm caches live here.";
    };
    suiteDir = lib.mkOption {
      type = lib.types.str;
      default = "/home/thomaseckert/Projects/Chill-Subs+Galley/t-eckert/csg/dev-suite";
      description = ''
        dev-suite directory. `fuzz-app` calls its run-with-env so the isolated
        apps get exactly the same env — including the fuzz .env.local
        credential overlays — as the process-compose copies.
      '';
    };
    csRoot = lib.mkOption {
      type = lib.types.str;
      default = "/home/thomaseckert/Projects/Chill-Subs+Galley/Chill-Subs";
      description = "Chill Subs checkout root holding chill-subs/ and chillest-subs/.";
    };
  };

  config = lib.mkIf cfg.enable {
    # IPAddressDeny/Allow compile to an eBPF cgroup/skb program attached to the
    # slice. The allow list is evaluated most-specific-first, so a broad
    # IPAddressDeny=any plus narrow allows gives default-deny egress.
    #
    # Note this filters by *address*, not hostname — which is the point. A
    # fuzzer that discovers a hostname still cannot route to it, and DNS itself
    # only resolves via MagicDNS inside the allowed 100.64.0.0/10.
    systemd.slices.fuzz = {
      description = "Network-isolated slice for adversarial/fuzz testing";
      sliceConfig = {
        IPAddressDeny = "any";
        IPAddressAllow = allowedDestinations ++ lib.optionals cfg.allowClerkAuth cfg.clerkAllowIPs;

        # Sized for what actually lives here: all three Next.js dev servers,
        # measured 2026-08-10 by PSS while running —
        #
        #   chillest-subs  2045 MB
        #   editor         2019 MB
        #   admin          1042 MB
        #   ------------------------
        #   total          ~5.1 GB
        #
        # An earlier 3G/4G pair was sized for a shell and would have OOM-killed
        # the apps as soon as the second one finished compiling. MemoryHigh
        # throttles first (reclaim, no kill) and MemoryMax is the hard stop,
        # deliberately below the 11G ceiling user-.slice gets in
        # memory-limits.nix so a runaway fuzz target dies here rather than
        # pushing the interactive session toward the global OOM killer.
        MemoryHigh = "6G";
        MemoryMax = "7G";
        TasksMax = 4096;
      };
    };

    # Passwordless sudo for the wrapper ONLY — never for systemd-run itself.
    #
    # fuzz-app takes a single argument matched against a fixed case statement
    # and hardcodes the unit, slice, uid, working directory and command. There
    # is no route from its argv to an arbitrary command, so this grants the
    # ability to start three specific dev servers in a network-isolated slice
    # and nothing more. `NOPASSWD: systemd-run` would instead have been a
    # one-line path to root.
    #
    # The rule names the /run/current-system path, not the /nix/store one.
    # sudo matches the command as resolved from PATH and does NOT follow
    # symlinks, so a store-path rule silently fails to match plain `fuzz-app`
    # and falls through to a password prompt — which looks exactly like a
    # missing rule (hit on 2026-08-10). The store path would pin exact
    # contents, but only root can retarget /run/current-system/sw/bin, and this
    # matches the existing workspace-init and marimo rules in this config.
    security.sudo.extraRules = [
      {
        users = [ cfg.user ];
        commands = [
          {
            command = "/run/current-system/sw/bin/fuzz-app";
            options = [
              "NOPASSWD"
              "SETENV"
            ];
          }
        ];
      }
    ];

    environment.systemPackages = [
      fuzzApp
      fuzzShell
      fuzzVerify
    ];
  };
}
