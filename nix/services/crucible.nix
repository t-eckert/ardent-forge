# nix/services/crucible.nix
{
  config,
  lib,
  pkgs,
  ...
}:

# A crucible is a vessel you put something in *because* you intend to subject it
# to conditions you would not apply in the open. This module is that vessel for
# workloads on this box: a named profile gets a systemd slice with default-deny
# egress, and only what you explicitly launch into it is affected.
#
# It generalises the fuzz-isolation module written on 2026-08-10 for the Chill
# Subs + Galley suite. That one hardcoded a single use case; this one takes
# profiles, so the next project gets containment without a new module.
#
# ── Why two layers ─────────────────────────────────────────────────────────
#
# Layer 1, the floor: systemd's IPAddressDeny/IPAddressAllow, which compile to
# an eBPF cgroup/skb program attached to the slice. Application code cannot talk
# its way past it. This layer is excellent at CIDR-shaped things -- the tailnet,
# the LAN, podman's networks, loopback -- because those are stable ranges.
#
# Layer 2, the allowlist: an egress proxy per profile, listening on loopback,
# allowing named hosts. This exists because of a hard limit in layer 1:
# **IPAddressAllow cannot take hostnames, only addresses and masks.** The
# predecessor module hit this and had to pin Clerk's Cloudflare IPs with a
# "these rotate, refresh with getent" note attached. That is not a wart to
# polish; it is the primitive reaching its ceiling. Every Cloudflare-fronted
# SaaS -- Clerk, Linear, most of them -- behaves that way, so an IP allowlist
# for SaaS is permanently unmaintainable.
#
# The two compose into a fail-closed system. The floor denies everything except
# infrastructure ranges and the loopback proxy. A process that honours
# HTTP(S)_PROXY reaches exactly the hosts its profile names. A process that
# ignores the proxy variables reaches *nothing*, because the floor still denies
# it -- it breaks loudly rather than escaping quietly, which is the correct
# failure for a containment tool.
#
# This mirrors what Anthropic's sandbox-runtime does for Claude Code (bwrap
# --unshare-net + a relay + a host proxy allowlisting by hostname, no TLS
# termination). Its documented limits apply here too and are worth knowing:
# domain fronting is possible, and a broad entry is a broad grant -- allowing
# "github.com" allows pushing to any repository on it.
#
# ── Why squid and not tinyproxy ────────────────────────────────────────────
#
# The proxy must allowlist the CONNECT target of an HTTPS tunnel by hostname,
# without terminating TLS. Tinyproxy is far smaller and was the first choice,
# but its documentation only commits to URL filtering working for plain HTTP
# and does not state whether domain filtering applies to CONNECT. Undefined
# semantics are not acceptable in the component doing the enforcing. Squid's
# `dstdomain` ACL against CONNECT is explicit, long-standing and widely relied
# upon, so the heavier dependency buys certainty. Caching is disabled -- this is
# a policy gate, not a cache.
#
# ── The user-unit trap, preserved from the predecessor ─────────────────────
#
# IPAddressDeny is **silently ignored in systemd user units**. Verified
# empirically on 2026-08-10: a user unit carrying IPAddressDeny=any reached
# s3.amazonaws.com (HTTP 307) exactly as freely as an unrestricted shell. A
# containment tool that quietly does nothing is worse than none, so everything
# this module launches goes into a transient *system* unit via `crucible-app`.

let
  cfg = config.ardentForge.crucible;

  # Stable CIDR blocks, named so profiles read as intent rather than numbers.
  tailnetCIDRs = [
    "100.64.0.0/10" # Tailscale CGNAT, and MagicDNS at 100.100.100.100
    "fd7a:115c:a1e0::/48" # Tailscale's IPv6 ULA -- resolv.conf lists a v6
    # nameserver alongside the v4 one, so omitting this
    # silently blocks the v6 resolver path.
  ];
  podmanCIDRs = [
    "10.88.0.0/16"
    "10.89.0.0/16"
  ];
  lanCIDRs = [ "192.168.0.0/16" ];

  # Each profile gets its own proxy on its own loopback port, so one profile's
  # allowlist can never serve another's workload. Ports are assigned by position
  # in the (alphabetically sorted) profile set. Adding a profile can therefore
  # shift the ports of later ones -- harmless, because every generated wrapper
  # and probe embeds the port at build time and they are all regenerated
  # together. Nothing outside this module should hardcode one.
  profileNames = lib.attrNames cfg.profiles;
  proxyPorts = lib.listToAttrs (
    lib.imap0 (i: n: lib.nameValuePair n (cfg.proxyBasePort + i)) profileNames
  );

  sliceNameOf = name: "crucible-${name}";

  # ── Per-profile derived values ─────────────────────────────────────────────

  allowedDestinationsOf =
    p:
    lib.optionals p.allowLoopback [ "localhost" ]
    ++ [ "link-local" ] # DHCP/IPv6 housekeeping; avoids odd stalls.
    ++ lib.optionals p.allowTailnet tailnetCIDRs
    ++ lib.optionals p.allowPodman podmanCIDRs
    ++ lib.optionals p.allowLAN lanCIDRs
    ++ p.allowCIDRs;

  usesProxy = p: p.allowHosts != [ ];

  squidConfOf =
    name: p:
    let
      port = proxyPorts.${name};
      # A leading dot makes squid match the domain and all subdomains, which is
      # what "allow linear.app" is nearly always meant to express. An entry that
      # already starts with a dot is passed through so a profile can be explicit.
      domainAcl = lib.concatMapStringsSep "\n" (
        h: "acl crucible_allowed dstdomain ${if lib.hasPrefix "." h then h else ".${h}"}"
      ) p.allowHosts;
    in
    pkgs.writeText "crucible-${name}-squid.conf" ''
      # Generated by ardentForge.crucible for profile "${name}". Do not edit.
      http_port 127.0.0.1:${toString port}

      acl crucible_connect method CONNECT
      acl crucible_safe_ports port 80 443
      ${domainAcl}

      # Order matters: deny unsafe ports and non-443 CONNECTs before the allow,
      # so a permitted domain cannot be used to reach an arbitrary port on it.
      http_access deny !crucible_safe_ports
      http_access deny crucible_connect !crucible_safe_ports
      http_access allow crucible_allowed
      http_access deny all

      # A policy gate, not a cache. No disk cache, nothing retained.
      cache deny all
      cache_store_log none
      pid_filename none
      access_log stdio:/dev/stdout
      cache_log stdio:/dev/stderr
      # Do not leak the client's address upstream. `via off` would also hide
      # that a proxy is involved, but squid warns "HTTP requires the use of Via"
      # on every start for it -- a permanent journal warning to conceal
      # something the upstream may infer anyway. Not worth it.
      forwarded_for delete
    '';

  # ── Wrappers ───────────────────────────────────────────────────────────────
  #
  # `crucible-app` is the only thing granted passwordless sudo, so its argv must
  # not reach an arbitrary command. It takes a profile name and an app name,
  # matches both against fixed case statements generated from the config, and
  # hardcodes the unit, slice, uid, directory, environment and command. There is
  # no path from its arguments to running something of the caller's choosing,
  # which is what makes the NOPASSWD rule safe. `NOPASSWD: systemd-run` would
  # instead have been a one-line path to root.
  #
  # sudo matches the command as resolved from PATH and does NOT follow symlinks,
  # so the sudoers rule below must name the /run/current-system path rather than
  # the /nix/store one. A store-path rule silently fails to match plain
  # `crucible-app` and falls through to a password prompt that looks exactly
  # like a missing rule (hit on 2026-08-10 with the predecessor).

  appCaseFor =
    name: p:
    let
      port = proxyPorts.${name};
      proxyEnv = lib.optionalString (usesProxy p) ''
        setenvs+=(--setenv=HTTP_PROXY=http://127.0.0.1:${toString port})
        setenvs+=(--setenv=HTTPS_PROXY=http://127.0.0.1:${toString port})
        setenvs+=(--setenv=http_proxy=http://127.0.0.1:${toString port})
        setenvs+=(--setenv=https_proxy=http://127.0.0.1:${toString port})
        setenvs+=(--setenv=NO_PROXY=${lib.escapeShellArg p.noProxy})
        setenvs+=(--setenv=no_proxy=${lib.escapeShellArg p.noProxy})
      '';
      profileEnv = lib.concatMapStringsSep "\n" (
        k: "setenvs+=(--setenv=${k}=${lib.escapeShellArg p.environment.${k}})"
      ) (lib.attrNames p.environment);
      apps = lib.attrNames p.apps;
      appCases = lib.concatMapStringsSep "\n" (a: ''
        ${a})
          dir=${lib.escapeShellArg p.apps.${a}.workingDirectory}
          cmd=${lib.escapeShellArg p.apps.${a}.command}
          ${lib.concatMapStringsSep "\n          " (
            k: "setenvs+=(--setenv=${k}=${lib.escapeShellArg p.apps.${a}.environment.${k}})"
          ) (lib.attrNames p.apps.${a}.environment)}
          ;;'') apps;
    in
    ''
      ${name})
        slice=${sliceNameOf name}.slice
        uid=${toString p.uid}
        gid=${toString p.gid}
        valid_apps=${lib.escapeShellArg (lib.concatStringsSep " " apps)}
        ${proxyEnv}
        ${profileEnv}
        case "$app" in
        ${appCases}
          *)
            echo "unknown app '$app' for profile '${name}' (have: $valid_apps)" >&2
            exit 2
            ;;
        esac
        ;;'';

  crucibleApp = pkgs.writeShellScriptBin "crucible-app" ''
    set -euo pipefail

    profile="''${1:-}"
    app="''${2:-}"
    action="''${3:-start}"

    if [ -z "$profile" ] || [ -z "$app" ]; then
      echo "usage: crucible-app <profile> <app> [start|stop|status]" >&2
      echo "profiles: ${lib.concatStringsSep " " profileNames}" >&2
      exit 2
    fi

    unit="crucible-$profile-$app"

    case "$action" in
      stop)   exec ${pkgs.systemd}/bin/systemctl stop "$unit.service" ;;
      status) exec ${pkgs.systemd}/bin/systemctl status "$unit.service" --no-pager ;;
      start)  : ;;
      *) echo "unknown action: $action" >&2; exit 2 ;;
    esac

    # Everything below is fixed by this script, never taken from argv.
    setenvs=()
    case "$profile" in
    ${lib.concatStringsSep "\n" (lib.mapAttrsToList appCaseFor cfg.profiles)}
      *)
        echo "unknown profile '$profile' (have: ${lib.concatStringsSep " " profileNames})" >&2
        exit 2
        ;;
    esac

    exec ${pkgs.systemd}/bin/systemd-run \
      --unit="$unit" \
      --slice="$slice" \
      --uid="$uid" --gid="$gid" \
      --working-directory="$dir" \
      --setenv=CRUCIBLE_PROFILE="$profile" \
      "''${setenvs[@]}" \
      --collect \
      -- ${pkgs.bashInteractive}/bin/bash -lc "$cmd"
  '';

  # Drop a shell (or any command) into a profile's slice.
  #
  # Deliberately NOT in the sudoers rule: it runs an arbitrary command, so it
  # must cost a password. Root is needed to create the transient unit at all --
  # systemd attaches the eBPF filter, so an unprivileged process cannot place
  # itself under a policy it could then escape. --uid hands the shell straight
  # back to the caller, so file ownership in the workspace is unchanged.
  crucibleShell = pkgs.writeShellScriptBin "crucible-shell" ''
    set -euo pipefail
    profile="''${1:-}"
    if [ -z "$profile" ]; then
      echo "usage: crucible-shell <profile> [command...]" >&2
      echo "profiles: ${lib.concatStringsSep " " profileNames}" >&2
      exit 2
    fi
    shift

    case "$profile" in
    ${lib.concatStringsSep "\n" (
      lib.mapAttrsToList (name: p: ''
        ${name})
          slice=${sliceNameOf name}.slice
          ${lib.optionalString (usesProxy p) ''
            proxy=http://127.0.0.1:${toString proxyPorts.${name}}
            noproxy=${lib.escapeShellArg p.noProxy}
          ''}
          ;;'') cfg.profiles
    )}
      *) echo "unknown profile '$profile'" >&2; exit 2 ;;
    esac

    if ! ${pkgs.systemd}/bin/systemctl cat "$slice" >/dev/null 2>&1; then
      echo "$slice is not defined -- is ardentForge.crucible.enable set?" >&2
      exit 1
    fi

    env=()
    if [ -n "''${proxy:-}" ]; then
      env+=(--setenv=HTTP_PROXY="$proxy"  --setenv=HTTPS_PROXY="$proxy")
      env+=(--setenv=http_proxy="$proxy"  --setenv=https_proxy="$proxy")
      env+=(--setenv=NO_PROXY="$noproxy"  --setenv=no_proxy="$noproxy")
    fi

    exec sudo ${pkgs.systemd}/bin/systemd-run \
      --slice="$slice" \
      --uid="''${SUDO_UID:-$(id -u)}" \
      --gid="''${SUDO_GID:-$(id -g)}" \
      --same-dir --pty --quiet --collect \
      --setenv=CRUCIBLE_PROFILE="$profile" \
      "''${env[@]}" \
      -- "''${@:-${pkgs.bashInteractive}/bin/bash}"
  '';

  # Each profile carries its own proof. `mustReach` is what the workload needs
  # in order to function; `mustNotReach` is what containment is *for*. Both are
  # asserted, because a shield that blocks everything including the things the
  # workload needs is not a working shield, it is a broken environment -- and
  # you want to find that out before a session, not during one.
  crucibleVerify = pkgs.writeShellScriptBin "crucible-verify" ''
    set -uo pipefail
    curl=${pkgs.curl}/bin/curl
    profile="''${CRUCIBLE_PROFILE:-''${1:-}}"

    if [ -z "$profile" ]; then
      echo "usage: crucible-verify <profile>            (from outside: expects normal egress)" >&2
      echo "       crucible-shell <profile> crucible-verify   (from inside: expects containment)" >&2
      exit 2
    fi

    if [ -n "''${CRUCIBLE_PROFILE:-}" ]; then
      echo "Running INSIDE $profile -- expecting containment."
      inside=1
    else
      echo "Running OUTSIDE the slice -- expecting normal egress."
      echo "(run 'crucible-shell $profile crucible-verify' to test the contained side)"
      inside=0
    fi

    rc=0
    probe() { # label url expect(ok|blocked)
      code=$($curl -s -o /dev/null -w '%{http_code}' -m 8 "$2" 2>/dev/null) || code="000"
      if [ "$3" = "ok" ]; then
        if [ "$code" != "000" ]; then echo "  PASS  $1 reachable ($code)"
        else echo "  FAIL  $1 unreachable -- the workload would break"; rc=1; fi
      else
        if [ "$code" = "000" ]; then echo "  PASS  $1 BLOCKED"
        else echo "  FAIL  $1 REACHABLE ($code) -- containment is not holding"; rc=1; fi
      fi
    }

    case "$profile" in
    ${lib.concatStringsSep "\n" (
      lib.mapAttrsToList (name: p: ''
        ${name})
          echo "-- must stay reachable --"
          ${lib.concatMapStringsSep "\n    " (
            u: "probe ${lib.escapeShellArg u} ${lib.escapeShellArg u} ok"
          ) p.verify.mustReach}
          echo "-- must not be reachable --"
          ${lib.concatMapStringsSep "\n    " (u: ''
            if [ "$inside" = "1" ]; then probe ${lib.escapeShellArg u} ${lib.escapeShellArg u} blocked
            else probe ${lib.escapeShellArg u} ${lib.escapeShellArg u} ok; fi'') p.verify.mustNotReach}
          ;;'') cfg.profiles
    )}
      *) echo "unknown profile '$profile'" >&2; exit 2 ;;
    esac
    exit $rc
  '';

  # ── Submodules ─────────────────────────────────────────────────────────────

  appType = lib.types.submodule {
    options = {
      workingDirectory = lib.mkOption {
        type = lib.types.str;
        description = "Directory the app is launched from.";
      };
      command = lib.mkOption {
        type = lib.types.str;
        example = "pnpm dev --turbopack -p 8000 -H 0.0.0.0";
        description = ''
          Command line, run through `bash -lc`. Fixed at build time and never
          taken from argv, which is what keeps the passwordless sudo rule for
          `crucible-app` from being a path to arbitrary root execution.
        '';
      };
      environment = lib.mkOption {
        type = lib.types.attrsOf lib.types.str;
        default = { };
        description = ''
          Extra environment for this app, merged over the profile's. System
          units inherit nothing from environment.d -- only the systemd *user*
          manager loads that -- so anything home-manager exports (PRISMA_* and
          friends) has to be named here explicitly. Omitting it fails at first
          use rather than at launch, which is a nasty way to lose an afternoon.
        '';
      };
    };
  };

  profileType = lib.types.submodule (
    { name, ... }:
    {
      options = {
        description = lib.mkOption {
          type = lib.types.str;
          default = "Crucible profile ${name}";
          description = "Shown in `systemctl status` for the slice.";
        };

        allowLoopback = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = ''
            Allow loopback. Required if `allowHosts` is used, since the egress
            proxy listens on 127.0.0.1. Note this grants the workload every
            other service on loopback too -- local databases included -- which
            is usually the intent for a dev suite and worth a thought otherwise.
          '';
        };
        allowTailnet = lib.mkOption {
          type = lib.types.bool;
          default = false;
          description = ''
            Allow the Tailscale ranges. Off by default *deliberately*: the
            predecessor module baked this in for one project that needed MinIO
            on the tailnet, but as a general default it hands every contained
            workload the whole tailnet, which is a large grant. Turn it on per
            profile, knowingly.
          '';
        };
        allowLAN = lib.mkOption {
          type = lib.types.bool;
          default = false;
          description = "Allow 192.168.0.0/16.";
        };
        allowPodman = lib.mkOption {
          type = lib.types.bool;
          default = false;
          description = "Allow podman's default rootless CNI networks.";
        };
        allowCIDRs = lib.mkOption {
          type = lib.types.listOf lib.types.str;
          default = [ ];
          description = ''
            Extra address ranges for the kernel floor. For CIDR-shaped
            infrastructure only -- use `allowHosts` for anything named, and
            never pin a Cloudflare-fronted SaaS here.
          '';
        };

        allowHosts = lib.mkOption {
          type = lib.types.listOf lib.types.str;
          default = [ ];
          example = [
            "api.linear.app"
            "api.anthropic.com"
          ];
          description = ''
            Hostnames reachable through this profile's egress proxy. A bare name
            matches the domain and its subdomains; write a leading dot to be
            explicit. Only ports 80 and 443 are permitted.

            Setting this at all stands up a squid instance for the profile and
            injects HTTP(S)_PROXY into everything launched into it. A process
            that ignores those variables reaches nothing rather than escaping,
            because the kernel floor still denies it.
          '';
        };
        noProxy = lib.mkOption {
          type = lib.types.str;
          default = "localhost,127.0.0.1,::1";
          description = "NO_PROXY value for workloads in this profile.";
        };

        environment = lib.mkOption {
          type = lib.types.attrsOf lib.types.str;
          default = { };
          description = "Environment applied to every app in this profile.";
        };

        uid = lib.mkOption {
          type = lib.types.int;
          default = 1000;
          description = "Numeric uid the contained apps run as.";
        };
        gid = lib.mkOption {
          type = lib.types.int;
          default = 100;
          description = "Numeric gid the contained apps run as.";
        };

        memoryHigh = lib.mkOption {
          type = lib.types.str;
          default = "6G";
          description = ''
            Soft cap -- throttles by reclaim, does not kill. Size this to what
            actually lives in the profile: the predecessor was first set to 3G
            for a shell and would have OOM-killed three Next.js dev servers
            whose measured PSS together was ~5.1 GB.
          '';
        };
        memoryMax = lib.mkOption {
          type = lib.types.str;
          default = "7G";
          description = ''
            Hard stop. Keep it below the ceiling user-.slice gets in
            memory-limits.nix, so a runaway contained workload dies here rather
            than pushing the interactive session toward the global OOM killer.
          '';
        };
        tasksMax = lib.mkOption {
          type = lib.types.int;
          default = 4096;
          description = "Task limit for the slice.";
        };

        apps = lib.mkOption {
          type = lib.types.attrsOf appType;
          default = { };
          description = "Apps launchable with `crucible-app <profile> <app>`.";
        };

        verify = {
          mustReach = lib.mkOption {
            type = lib.types.listOf lib.types.str;
            default = [ ];
            example = [ "http://localhost:8000/" ];
            description = "URLs the workload needs. Asserted reachable on both sides.";
          };
          mustNotReach = lib.mkOption {
            type = lib.types.listOf lib.types.str;
            default = [ ];
            example = [ "https://s3.amazonaws.com" ];
            description = ''
              The sinks containment exists to prevent. Asserted blocked inside
              the slice and reachable outside it -- if the "outside" half fails,
              the probe itself is broken and the inside result proves nothing.
            '';
          };
        };
      };
    }
  );
in
{
  options.ardentForge.crucible = {
    enable = lib.mkEnableOption ''
      network-contained systemd slices for workloads that must not touch
      production. Defining a profile costs nothing until something is launched
      into it with `crucible-app` or `crucible-shell`, so this is meant to be
      left on
    '';

    proxyBasePort = lib.mkOption {
      type = lib.types.port;
      default = 3128;
      description = ''
        First loopback port for per-profile egress proxies; profiles are
        assigned sequentially from here. Nothing outside this module should
        hardcode one -- the wrappers embed the right port at build time.
      '';
    };

    profiles = lib.mkOption {
      type = lib.types.attrsOf profileType;
      default = { };
      description = "Named containment profiles.";
    };

    sudoUsers = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      description = ''
        Users granted passwordless sudo for `crucible-app` only. That wrapper
        cannot run an arbitrary command, so this grants the ability to start
        the declared apps in their slices and nothing more. `crucible-shell` is
        deliberately excluded and always costs a password.
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    assertions = lib.mapAttrsToList (name: p: {
      assertion = usesProxy p -> p.allowLoopback;
      message = ''
        ardentForge.crucible.profiles.${name} sets allowHosts but disables
        allowLoopback. The egress proxy listens on 127.0.0.1, so the profile
        could never reach it and every allowed host would be unreachable.
      '';
    }) cfg.profiles;

    # The allow list is evaluated most-specific-first, so a broad
    # IPAddressDeny=any plus narrow allows gives default-deny egress.
    #
    # Note this filters by *address*, not hostname -- which is the point at this
    # layer. A workload that discovers a hostname still cannot route to it, and
    # DNS resolves only via whatever the allowed ranges reach.
    systemd.slices = lib.mapAttrs' (
      name: p:
      lib.nameValuePair (sliceNameOf name) {
        inherit (p) description;
        sliceConfig = {
          IPAddressDeny = "any";
          IPAddressAllow = allowedDestinationsOf p;
          MemoryHigh = p.memoryHigh;
          MemoryMax = p.memoryMax;
          TasksMax = p.tasksMax;
        };
      }
    ) cfg.profiles;

    # Proxies run OUTSIDE the crucible slices -- they are the one component that
    # legitimately needs real egress, and containing them would defeat them.
    systemd.services = lib.mapAttrs' (
      name: p:
      lib.nameValuePair "crucible-proxy-${name}" {
        description = "Crucible egress allowlist proxy for profile ${name}";
        wantedBy = [ "multi-user.target" ];
        after = [ "network-online.target" ];
        wants = [ "network-online.target" ];
        serviceConfig = {
          ExecStart = "${pkgs.squid}/bin/squid -N -f ${squidConfOf name p}";
          Restart = "on-failure";
          DynamicUser = true;
          RuntimeDirectory = "crucible-proxy-${name}";
          # The proxy holds no secrets and touches no persistent state; give it
          # the standard hardening so a flaw in it is not a way onto the box.
          NoNewPrivileges = true;
          PrivateTmp = true;
          PrivateDevices = true;
          ProtectSystem = "strict";
          ProtectHome = true;
          ProtectKernelTunables = true;
          ProtectKernelModules = true;
          ProtectControlGroups = true;
          RestrictAddressFamilies = [
            "AF_INET"
            "AF_INET6"
          ];
          RestrictNamespaces = true;
          LockPersonality = true;
          MemoryDenyWriteExecute = true;
        };
      }
    ) (lib.filterAttrs (_: usesProxy) cfg.profiles);

    security.sudo.extraRules = lib.optionals (cfg.sudoUsers != [ ]) [
      {
        users = cfg.sudoUsers;
        commands = [
          {
            command = "/run/current-system/sw/bin/crucible-app";
            options = [
              "NOPASSWD"
              "SETENV"
            ];
          }
        ];
      }
    ];

    environment.systemPackages = [
      crucibleApp
      crucibleShell
      crucibleVerify
    ];
  };
}
