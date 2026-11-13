# nix/remote-control.nix
#
# `claude remote-control` servers, so sessions can be started on this box from
# claude.ai/code or the Claude app. Each server is bound to one directory:
# every session spawned from the UI starts there, and that directory's
# .claude/settings.json, hooks, CLAUDE.md and project memory are what it gets.
# So there is one instance per repo rather than one in ~.
#
# This is a template, and the instances are not declared here. Which repos get
# one is host state, and most of them are private while this repo is public --
# the same reason the workspace repo list lives in 1Password. Enable one with
# the repo's path relative to $HOME, escaped:
#
#   systemctl --user enable --now \
#     "claude-rc@$(systemd-escape --path Repos/github.com/OWNER/REPO).service"
#
# and list what is enabled with `systemctl --user list-units 'claude-rc@*'`.
# The enablement symlink lives in ~/.config/systemd/user/default.target.wants,
# which home-manager does not own, so it survives switches.
#
# Run `claude` in the repo once by hand before enabling it: a folder has to be
# trusted, and a unit has no terminal to answer the prompt on.
#
# --spawn=worktree gives each session started from the UI its own git
# worktree, so parallel sessions don't share a working tree. The pre-created
# session stays in the checkout itself. Permission mode is not set here, so
# sessions follow ~/.claude/settings.json and the repo's own settings.
#
# A user unit for the same reasons as alert-triage: `claude` authenticates
# from ~/.claude/.credentials.json. Lingering is enabled, so the servers come
# up at boot without anyone logged in.
{ config, pkgs, lib, ... }:

let
  # A user unit does not source the login shell, so claude (~/.local/bin) and
  # the per-user profile have to be put on PATH explicitly. Sessions inherit
  # this PATH for the tools they run.
  path = "${config.home.homeDirectory}/.local/bin:/run/current-system/sw/bin:/etc/profiles/per-user/${config.home.username}/bin";
in
{
  # Written as a plain file rather than through systemd.user.services: given an
  # [Install] section there, home-manager links the bare template into
  # default.target.wants, which systemd cannot start and warns about. The
  # [Install] section is still needed for `systemctl --user enable` to work.
  #
  # Because home-manager does not track this as a unit, a change here does not
  # restart running instances: `systemctl --user restart 'claude-rc@*'`.
  xdg.configFile."systemd/user/claude-rc@.service".text = ''
    [Unit]
    Description=Claude Remote Control in ~/%I
    After=network-online.target
    # A missing login or an untrusted folder fails every time; stop retrying
    # after a few rather than restarting forever.
    StartLimitIntervalSec=600
    StartLimitBurst=5

    [Service]
    Environment=PATH=${path}
    WorkingDirectory=%h/%I
    # Named after the repo's directory, which is what claude.ai/code shows.
    ExecStart=${pkgs.bash}/bin/bash -c 'exec claude remote-control --name "$(basename "$$PWD")" --spawn=worktree'
    Restart=on-failure
    RestartSec=30

    [Install]
    WantedBy=default.target
  '';
}
