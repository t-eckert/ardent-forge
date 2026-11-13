# nix/services/github-pat-credential.nix
#
# A git credential helper that answers with the `github-pat` token, read from
# 1Password each time git asks. Used by notebook-sync and lab-sync.
#
# Reading it on demand, not once at service start, is what lets the token be
# rotated in 1Password with nothing done on the box: the services hold no copy
# of it. They put git's in-memory credential cache in front of this helper so
# 1Password is not asked every sync. When GitHub rejects a cached token, git
# erases it from the cache, and the next sync comes back here for the new one.
#
# Needs OP_SERVICE_ACCOUNT_TOKEN in the environment; the services get it from
# /etc/ardent-forge/op-token. Usage, with the cache socket in a 0700 directory:
#
#   git config credential.helper ""
#   git config --add credential.helper "cache --timeout=3600 --socket=<dir>/socket"
#   git config --add credential.helper "${helper}"
{ pkgs }:

pkgs.writeShellScript "github-pat-credential" ''
  # git writes the request on stdin; read it so git never hits a closed pipe.
  cat >/dev/null
  # git calls helpers with get, store or erase. Only get needs an answer.
  [ "''${1:-}" = get ] || exit 0
  token=$(${pkgs._1password-cli}/bin/op read "op://Ardent Forge/github-pat/credential") || exit 0
  echo username=x-access-token
  echo "password=$token"
''
