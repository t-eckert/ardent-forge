# nix/claude-code.nix
#
# Claude Code skills and hook scripts that only make sense on this box,
# installed under ~/.claude where every session run here finds them.
#
#   ./claude-skills/<name>/   one skill: a SKILL.md and the scripts it calls,
#                             installed as ~/.claude/skills/<name>/
#   ./claude-hooks/<script>   a hook script, installed as ~/.claude/hooks/<script>
#
# Adding one is adding a file; it has to be `git add`ed before a build sees
# it, and a script keeps its executable bit from git.
#
# A hook script does nothing until ~/.claude/settings.json names it under
# `hooks`. Claude Code rewrites that file itself, so it is not managed here:
# on a fresh install the entries are added by hand. zellij-attention runs as
# `mark` on Stop and Notification, and as `clear` on UserPromptSubmit,
# PostToolUse and SessionEnd.
#
# Every file is forced. Without it home-manager refuses to switch when a
# file that differs is already at the target, so a copy edited in place on
# the box would fail the next deploy. The repo wins: edit the copy here.
{ lib, ... }:

let
  entries = dir: lib.attrNames (builtins.readDir dir);
  install = target: source: {
    name = target;
    value = {
      inherit source;
      force = true;
    };
  };

  skillsRoot = ./claude-skills;
  skills = lib.filter (name: (builtins.readDir skillsRoot).${name} == "directory") (
    entries skillsRoot
  );
  skillFiles = lib.concatMap (
    skill:
    map (file: install ".claude/skills/${skill}/${file}" (skillsRoot + "/${skill}/${file}")) (
      entries (skillsRoot + "/${skill}")
    )
  ) skills;

  hooksRoot = ./claude-hooks;
  hookFiles = map (file: install ".claude/hooks/${file}" (hooksRoot + "/${file}")) (
    entries hooksRoot
  );
in
{
  home.file = lib.listToAttrs (skillFiles ++ hookFiles);
}
