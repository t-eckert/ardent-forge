# nix/claude-skills.nix
#
# Claude Code skills that only make sense on this box, installed into
# ~/.claude/skills where every session run here finds them. Each directory
# under ./claude-skills is one skill: a SKILL.md and the scripts it calls.
# Adding a skill is adding a directory; a new file has to be `git add`ed
# before a build sees it, and a script keeps its executable bit from git.
#
# Every file is forced. Without it home-manager refuses to switch when a
# file that differs is already at the target, so a skill edited in place on
# the box would fail the next deploy. The repo wins: edit the copy here.
{ lib, ... }:

let
  root = ./claude-skills;
  entries = dir: lib.attrNames (builtins.readDir dir);
  skills = lib.filter (name: (builtins.readDir root).${name} == "directory") (entries root);
in
{
  home.file = lib.listToAttrs (
    lib.concatMap (
      skill:
      map (file: {
        name = ".claude/skills/${skill}/${file}";
        value = {
          source = root + "/${skill}/${file}";
          force = true;
        };
      }) (entries (root + "/${skill}"))
    ) skills
  );
}
