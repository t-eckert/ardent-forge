# nix/claude-code.nix
#
# Box-wide Claude Code policy, written to /etc/claude-code/managed-settings.json.
#
# Managed settings are the one settings file every `claude` process on the box
# reads, however it was started: over SSH/mosh, from the Claude Code UI, or
# unattended by alert-triage and add-weather. ~/.claude/settings.json is not
# that file — it is hand-edited (the dotfiles profile is null on Linux) and a
# session started some other way can miss it, which is how sessions were
# dropping off the Claude Code dashboard. Hooks declared here merge with any
# in the user's own settings rather than replacing them.
#
# The SessionStart hook writes one JSON line per session to the journal under
# the identifier `claude-code-session`. Alloy already ships the journal to
# Loki and relabels that identifier to job="claude-code-sessions" (see
# nix/services/monitoring.nix); the "Session starts" table on the Claude Code
# dashboard reads it from there.
#
# The hook must stay silent and must never fail. SessionStart stdout is fed to
# the model as context, so nothing may reach stdout; and a hook error would be
# shown to the user on every session start. Hence the redirects, `|| true`
# and unconditional `exit 0`.
{ pkgs, ... }:

let
  sessionStartHook = pkgs.writeShellApplication {
    name = "claude-code-session-start";
    runtimeInputs = with pkgs; [ jq systemd ];
    # writeShellApplication turns on errexit/pipefail; the hook opts back out
    # because a failed log line must not become a failed session start.
    text = ''
      set +e +o pipefail

      ssh=false
      if [[ -n "''${SSH_CONNECTION:-}" ]]; then ssh=true; fi

      # Hook input arrives on stdin. The env vars are set by Claude Code in its
      # own process and inherited by hooks; each may be absent, so default to
      # empty rather than letting `set -u` trip.
      jq -c \
        --arg entrypoint "''${CLAUDE_CODE_ENTRYPOINT:-}" \
        --arg remote "''${CLAUDE_CODE_REMOTE:-}" \
        --arg bridge "''${CLAUDE_CODE_BRIDGE_SESSION_ID:-}" \
        --argjson ssh "$ssh" \
        --arg user "$(id -un)" \
        '{
          event: "session_start",
          session_id,
          source,
          cwd,
          transcript_path,
          model: (.model // null),
          entrypoint: $entrypoint,
          remote: $remote,
          bridge_session_id: $bridge,
          ssh: $ssh,
          user: $user
        }' 2>/dev/null \
        | systemd-cat -t claude-code-session -p info >/dev/null 2>&1

      exit 0
    '';
  };

  managedSettings = {
    hooks.SessionStart = [
      {
        # No matcher: log startup, resume, clear, compact and fork alike. The
        # `source` field in the line says which.
        hooks = [
          {
            type = "command";
            command = "${sessionStartHook}/bin/claude-code-session-start";
            async = true;
            timeout = 10;
          }
        ];
      }
    ];
  };
in
{
  environment.etc."claude-code/managed-settings.json".text = builtins.toJSON managedSettings;
}
