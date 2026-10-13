# nix/add-weather.nix
#
# Once a day, refresh the weather in the Notebook's daily logs by running its
# /add-weather command through `claude -p`. The command writes a `weather:`
# frontmatter key into Log/ for today and the next seven days; syncshot then
# commits and pushes those edits like any other.
#
# A user unit for the same reasons as alert-triage: `claude` authenticates from
# ~/.claude/.credentials.json, and the OpenWeather key lives in the Notebook's
# gitignored .env, which the command reads relative to its working directory.
# Lingering is enabled, so it runs without anyone logged in.
#
# The tool allowlist covers what the command does and nothing else: read and
# edit files, curl the API, and parse the response. git is denied outright --
# committing is syncshot's job, and a hand commit would race it.
{ config, pkgs, lib, ... }:

let
  notebook = "/data/ardent-forge/notebook";
  allowed = [
    "Read" "Edit" "Write" "Glob" "Grep"
    "Bash(curl:*)" "Bash(grep:*)" "Bash(cut:*)" "Bash(tr:*)"
    "Bash(jq:*)" "Bash(python3:*)" "Bash(date:*)" "Bash(ls:*)" "Bash(cat:*)"
  ];
  denied = [ "Bash(git:*)" "Bash(rm:*)" "Bash(sudo:*)" ];
in
{
  systemd.user.services.add-weather = {
    Unit = {
      Description = "Refresh weather in the Notebook's daily logs";
      After = [ "network-online.target" ];
    };
    Service = {
      Type = "oneshot";
      # A user unit does not source the login shell, so claude (~/.local/bin)
      # and the per-user profile have to be put on PATH explicitly.
      Environment = [
        "PATH=${config.home.homeDirectory}/.local/bin:/run/current-system/sw/bin:/etc/profiles/per-user/${config.home.username}/bin"
      ];
      WorkingDirectory = notebook;
      ExecStart = lib.escapeShellArgs [
        "claude" "-p" "/add-weather"
        "--allowedTools" (lib.concatStringsSep "," allowed)
        "--disallowedTools" (lib.concatStringsSep "," denied)
      ];
      # One API call and eight small file edits. The cap only exists so a
      # wedged run cannot hold the unit indefinitely.
      TimeoutStartSec = "15min";
    };
  };

  systemd.user.timers.add-weather = {
    Unit.Description = "Daily weather refresh for the Notebook";
    Timer = {
      # Early enough that today's log has the forecast before the day starts.
      # Persistent catches up a run missed while the box was down.
      OnCalendar = "*-*-* 05:00:00";
      Persistent = true;
      Unit = "add-weather.service";
    };
    Install.WantedBy = [ "timers.target" ];
  };
}
