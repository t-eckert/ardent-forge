# The NixOS module for the implementer: one systemd unit per process.
#
# Each process gets its own Unix user and state directory, so no process can read another's SQLite file, and its own
# environment file and wrapper, so it only ever receives its own credentials. On the Forge the wrapper is
# `op run --env-file <file> --`, and the egress fence is a crucible profile applied in ardent-forge. See
# docs/design.md, "Packaging and deploys".
self:
{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.services.implementer;
  inherit (lib) mkOption mkEnableOption types;

  processOptions =
    { name, ... }:
    {
      options = {
        enable = mkEnableOption "the implementer ${name} process";

        graceSeconds = mkOption {
          type = types.ints.unsigned;
          default = 30;
          description = "How long in-flight work gets to reach a checkpoint after SIGTERM.";
        };

        wrapper = mkOption {
          type = types.listOf types.str;
          default = [ ];
          example = [ "op" "run" "--env-file" "/etc/implementer/implementer.env" "--" ];
          description = "Command that `implementer run` is executed under, such as `op run` to inject this process's secrets.";
        };

        environmentFile = mkOption {
          type = types.nullOr types.path;
          default = null;
          description = "systemd EnvironmentFile for this process, such as the 1Password service account token.";
        };

        path = mkOption {
          type = types.listOf types.package;
          default = [ ];
          description = "Packages on the unit's PATH, such as the 1Password CLI the wrapper needs.";
        };

        serviceConfig = mkOption {
          type = types.attrsOf types.anything;
          default = { };
          example = { MemoryMax = "6G"; Slice = "crucible-implementer.slice"; };
          description = "Extra systemd [Service] settings, such as a memory limit or a crucible slice.";
        };
      };
    };

  # The close deadline in src/cli.ts, plus a margin, so implementer always ends itself before systemd sends SIGKILL.
  closeDeadlineSeconds = 15;
  stopMarginSeconds = 10;

  # The implementer runs a rootless Podman container per session, which needs more from its unit than the other
  # processes: a fixed uid with lingering, so /run/user/<uid> exists; subuid ranges; Delegate=yes, so
  # `--cgroups=split` can keep the containers inside the unit's cgroup and its limits; and no NoNewPrivileges, which
  # would stop the setuid newuidmap that rootless Podman relies on. See docs/design.md, "Isolating a session".
  implementerRuntimeDir = "/run/user/${toString cfg.implementerUid}";
  sessionImage = "localhost/implementer-session:latest";
  proxied = cfg.implementerProxy != null;
  # When proxied, the fence probe runs in its own oneshot unit before every start, not as an ExecStartPre: the
  # probe's `podman run --cgroups=split` enables controllers in the calling unit's cgroup and moves its caller into a
  # child, after which cgroup v2 refuses to place ExecStart in the unit's root and systemd fails with EBUSY.
  implementerDeps = [ "implementer-session-image.service" ] ++ lib.optional proxied "implementer-probe.service";
  implementerUnit = {
    requires = implementerDeps;
    after = implementerDeps;
    path = [
      pkgs.podman
      "/run/wrappers"
    ];
    serviceConfig = {
      User = "implementer";
      Group = "implementer";
      Delegate = true;
      NoNewPrivileges = false;
      Environment = [
        "XDG_RUNTIME_DIR=${implementerRuntimeDir}"
        "IMPLEMENTER_SESSION_IMAGE=${sessionImage}"
      ]
      ++ lib.optionals proxied [
        "IMPLEMENTER_PROXY=${cfg.implementerProxy}"
        # The implementer itself reaches Linear, GitHub and the model API through the same proxy. Node's fetch ignores
        # these variables unless NODE_USE_ENV_PROXY is set.
        "NODE_USE_ENV_PROXY=1"
        "HTTP_PROXY=${cfg.implementerProxy}"
        "HTTPS_PROXY=${cfg.implementerProxy}"
        "NO_PROXY=localhost,127.0.0.1,::1"
      ];
      ReadWritePaths = [
        "${cfg.stateDir}/implementer"
        implementerRuntimeDir
      ];
      # Measured on the Forge on 2026-11-04: a Rust workspace's checks peak at 3.1 GiB from a cold cache and 1.1 GiB
      # warm. MemoryHigh throttles before MemoryMax kills, so a runaway build slows down first.
      MemoryHigh = "4G";
      MemoryMax = "5G";
    };
  };

  unitFor =
    name: p:
    let
      implementer = lib.getExe cfg.package;
      stateArgs = [ "--state-dir" cfg.stateDir ];
      extra = lib.optionalAttrs (name == "implementer") implementerUnit;
    in
    lib.nameValuePair "implementer-${name}" {
      description = "implementer ${name}";
      wantedBy = [ "multi-user.target" ];
      wants = [ "network-online.target" ];
      path = p.path ++ (extra.path or [ ]);
      requires = extra.requires or [ ];
      after = [ "network-online.target" ] ++ (extra.after or [ ]);

      serviceConfig = {
        Type = "simple";
        User = "implementer-${name}";
        Group = "implementer";
        # A snapshot before every start, so a schema migration in a new release can be rolled back.
        ExecStartPre = [
          (lib.escapeShellArgs ([ implementer "backup" "--local" name ] ++ stateArgs))
        ];
        ExecStart = lib.escapeShellArgs (
          p.wrapper ++ [ implementer "run" name "--grace" (toString p.graceSeconds) ] ++ stateArgs
        );
        KillSignal = "SIGTERM";
        # Only the main process gets SIGTERM; implementer stops its own children as part of its graceful exit.
        KillMode = "mixed";
        TimeoutStopSec = p.graceSeconds + closeDeadlineSeconds + stopMarginSeconds;
        Restart = "on-failure";
        RestartSec = 10;
        NoNewPrivileges = true;
        PrivateTmp = true;
        ProtectSystem = "strict";
        ReadWritePaths = [ "${cfg.stateDir}/${name}" ];
      }
      // (extra.serviceConfig or { })
      // lib.optionalAttrs (p.environmentFile != null) { EnvironmentFile = p.environmentFile; }
      // p.serviceConfig;
    };

  enabled = lib.filterAttrs (_: p: p.enable) cfg.processes;
in
{
  options.services.implementer = {
    package = mkOption {
      type = types.package;
      default = self.packages.${pkgs.stdenv.hostPlatform.system}.implementer;
      description = "The implementer package.";
    };

    stateDir = mkOption {
      type = types.str;
      default = "/data/implementer";
      description = "Root of implementer's state. Each process keeps its database, lock and snapshots in a subdirectory.";
    };

    implementerProxy = mkOption {
      type = types.nullOr types.str;
      default = null;
      example = "http://127.0.0.1:3128";
      description = ''
        The implementer's egress proxy, such as its crucible profile's. Sessions and the implementer itself go out
        through it, and the implementer runs `implementer probe` before it starts.
      '';
    };

    implementerUid = mkOption {
      type = types.ints.positive;
      default = 2741;
      description = "The implementer's uid. Fixed, because its rootless Podman needs /run/user/<uid>.";
    };

    processes = mkOption {
      type = types.attrsOf (types.submodule processOptions);
      default = { };
      description = "implementer's processes: gateway and implementer.";
    };
  };

  config = lib.mkIf (enabled != { }) {
    assertions = [
      {
        assertion = lib.all (n: lib.elem n [ "gateway" "implementer" ]) (lib.attrNames cfg.processes);
        message = "services.implementer.processes only knows gateway and implementer.";
      }
    ];

    users.groups.implementer = { };
    users.users = lib.mapAttrs' (
      name: _:
      lib.nameValuePair "implementer-${name}" (
        {
          isSystemUser = true;
          group = "implementer";
        }
        // lib.optionalAttrs (name == "implementer") {
          uid = cfg.implementerUid;
          # Podman keeps its images and containers under the home directory.
          home = "${cfg.stateDir}/implementer/home";
          createHome = true;
          linger = true;
          autoSubUidGidRange = true;
        }
      )
    ) enabled;

    systemd.tmpfiles.rules = [ "d ${cfg.stateDir} 0755 root root -" ]
      ++ lib.mapAttrsToList (name: _: "d ${cfg.stateDir}/${name} 0700 implementer-${name} implementer -") enabled;

    systemd.services =
      lib.mapAttrs' unitFor enabled
      // lib.optionalAttrs (enabled ? implementer) {
        # Builds the session image into the implementer's own Podman storage. It runs outside the implementer's fence,
        # since it pulls base images from Docker Hub, and reuses Podman's layer cache, so a deploy that does not change
        # the Containerfile takes seconds.
        implementer-session-image = {
          description = "Build implementer's session image";
          wants = [ "network-online.target" ];
          after = [
            "network-online.target"
            "user@${toString cfg.implementerUid}.service"
          ];
          requires = [ "user@${toString cfg.implementerUid}.service" ];
          path = [
            pkgs.podman
            "/run/wrappers"
          ];
          environment.XDG_RUNTIME_DIR = implementerRuntimeDir;
          serviceConfig = {
            Type = "oneshot";
            RemainAfterExit = true;
            User = "implementer";
            Group = "implementer";
            ExecStart = lib.escapeShellArgs [
              (lib.getExe pkgs.podman)
              "build"
              "--tag"
              sessionImage
              "${cfg.package}/share/implementer/images/session"
            ];
            TimeoutStartSec = "30min";
          };
        };
      }
      // lib.optionalAttrs (enabled ? implementer && proxied) {
        # The fence probe, before the implementer takes any work. If the fence does not hold, the implementer does not
        # start. It runs as the implementer, with the same delegation and environment and in the same slice, since the
        # fence is the slice's; see implementerDeps for why it is not an ExecStartPre.
        implementer-probe = {
          description = "Probe the implementer's fence";
          requires = [ "implementer-session-image.service" ];
          after = [ "implementer-session-image.service" ];
          inherit (implementerUnit) path;
          serviceConfig = {
            Type = "oneshot";
            inherit (implementerUnit.serviceConfig)
              User
              Group
              Delegate
              NoNewPrivileges
              Environment
              ReadWritePaths
              ;
            ExecStart = lib.escapeShellArgs [
              (lib.getExe cfg.package)
              "probe"
              "--state-dir"
              cfg.stateDir
            ];
            PrivateTmp = true;
            ProtectSystem = "strict";
          }
          // lib.optionalAttrs (cfg.processes.implementer.serviceConfig ? Slice) {
            inherit (cfg.processes.implementer.serviceConfig) Slice;
          };
        };
      };
  };
}
