# nix/services/opencode.nix
#
# OpenCode's server and web UI, for remote development from a browser on the
# laptop or the phone at https://code.<tailnet> (the `code` entry in caddy.nix).
#
# Interactive, not unattended: it runs as the user and edits anything under
# ~, the same trust as a Claude Code session over SSH. Anything left to run on
# its own belongs behind crucible, like stet.
#
# Access, in three layers:
#   - The server listens on 127.0.0.1 only. OpenCode has no TLS of its own, so
#     Caddy's tsnet node is the only way in, with Tailscale's certificate.
#   - Every /api path needs the server's credential. A browser gets one by
#     pairing: `opencode pair --url https://code.<tailnet>` over SSH prints a
#     one-time link and a QR code that expire in five minutes.
#   - Shell commands and edits ask before running (opencodeConfig below).
#
# Never run `opencode pair --remote`: it exposes the server to the internet
# through OpenCode's own tunnel.
#
# Model credentials come from `opencode auth login`, run once by hand; they
# live in OpenCode's data directory under ~/.local/share/opencode.
{ pkgs, lib, locals, ... }:

let
  home = "/home/${locals.username}";
  port = 4096;

  # Applied by the server, and by the CLI in a shell through OPENCODE_CONFIG,
  # so both read the same rules. A ~/.config/opencode/opencode.json, if one
  # appears, merges on top.
  opencodeConfig = pkgs.writeText "opencode.json" (builtins.toJSON {
    "$schema" = "https://opencode.ai/config.json";
    # Sessions never leave the box. "manual" would let one click upload a
    # session to OpenCode's servers.
    share = "disabled";
    # Nix owns the version; the package already sets OPENCODE_DISABLE_AUTOUPDATE.
    update = "disable";
    # Last matching rule wins. These match the build agent's own defaults
    # today; stating them here keeps them if a release loosens the defaults.
    permissions = [
      { action = "shell"; resource = "*"; effect = "ask"; }
      { action = "edit";  resource = "*"; effect = "ask"; }
    ];
  });
in
{
  # The same binary in a shell, so `opencode pair` and the TUI talk to this
  # server: `serve --service` registers itself where the CLI looks for the
  # background service, and the CLI attaches to it instead of starting its own.
  environment.systemPackages = [ pkgs.opencode ];
  environment.variables.OPENCODE_CONFIG = "${opencodeConfig}";

  systemd.services.opencode = {
    description = "OpenCode — server and web UI (code.*)";
    wantedBy = [ "multi-user.target" ];
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];

    environment = {
      HOME = home;
      OPENCODE_CONFIG = "${opencodeConfig}";
      # The tools the agent's shell commands find: the user's profile, then the
      # system's, replacing the minimal PATH systemd gives every unit.
      # /run/wrappers is left out on purpose; sudo could not work under
      # NoNewPrivileges anyway.
      PATH = lib.mkForce "/etc/profiles/per-user/${locals.username}/bin:/run/current-system/sw/bin";
    };

    serviceConfig = {
      Type = "simple";
      User = locals.username;
      Group = "users";
      WorkingDirectory = home;

      ExecStart = "${pkgs.opencode}/bin/opencode serve --service --hostname 127.0.0.1 --port ${toString port}";

      Restart = "on-failure";
      RestartSec = 10;

      # Writes anywhere under ~ (that is the point), nowhere else on the system.
      NoNewPrivileges = true;
      ProtectSystem = "strict";
      ReadWritePaths = [ home ];
      PrivateTmp = true;

      # The agent's builds and test runs land in this unit's cgroup, in
      # system.slice, outside the user.slice ceiling in memory-limits.nix.
      # MemoryHigh throttles and reclaims; it never kills.
      MemoryHigh = "6G";
    };
  };

  security.sudo.extraRules = [{
    users = [ locals.username ];
    commands = [
      { command = "/run/current-system/sw/bin/systemctl restart opencode"; options = [ "NOPASSWD" ]; }
      { command = "/run/current-system/sw/bin/systemctl stop opencode"; options = [ "NOPASSWD" ]; }
      { command = "/run/current-system/sw/bin/systemctl start opencode"; options = [ "NOPASSWD" ]; }
    ];
  }];
}
