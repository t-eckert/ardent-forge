# af: operate this box. Installed by nix/services/deploy.nix, which substitutes
# the @...@ values. Deploys run as root in af-rebuild.service; everything else
# here runs as the caller.

repo_url="@repoUrl@"
dev_checkout="@devCheckout@"
host="@host@"
state=/var/lib/af-rebuild/state.json
locals=/etc/ardent-forge/locals.json
repos_copy=/var/lib/workspace-init/repos # written by workspace-init on each run
repos_ref="op://Ardent Forge/workspace-repos/notesPlain"
systemctl=/run/current-system/sw/bin/systemctl # the path the sudo rules name

usage() {
  cat <<'EOF'
usage: af <command>

Box
  deploy [--retry]        deploy origin/main now and wait (--retry: a commit that failed)
  status                  what is running, what origin/main is, the last result
  log [N]                 the last N lines of deploy logs (default 80)
  config show|edit        show or edit /etc/ardent-forge/locals.json; edit deploys after
  repos list|sync         the repos workspace-init clones into ~/Repos/github.com
  repos add|remove o/r    edit that list (in 1Password) and sync

Development (in your checkout)
  build                   build the system from the checkout, as the pre-push hook does
  update [input...]       update flake inputs in the checkout and build; review, commit, push
  pins [--update]         report or refresh pins kept outside flake.lock
EOF
}

die() {
  echo "af: $*" >&2
  exit 1
}

checkout() {
  if [ -n "${AF_REPO:-}" ]; then
    echo "$AF_REPO"
    return
  fi
  local top
  if top=$(git rev-parse --show-toplevel 2>/dev/null) && [ -f "$top/nix/flake.nix" ] && [ -d "$top/nix/services/deploy" ]; then
    echo "$top"
    return
  fi
  [ -d "$dev_checkout/.git" ] || die "no checkout at $dev_checkout (set AF_REPO, or run from inside one)"
  echo "$dev_checkout"
}

short() { echo "${1:0:7}"; }

cmd_status() {
  local running origin
  running=$(nixos-version --configuration-revision 2>/dev/null || true)
  origin=$(git ls-remote "$repo_url" refs/heads/main 2>/dev/null | cut -f1 || true)
  echo "running     $(short "${running:-unknown}")"
  if [ -z "$origin" ]; then
    echo "origin/main (unreachable)"
  elif [ "$origin" = "$running" ]; then
    echo "origin/main $(short "$origin")  up to date"
  else
    local next
    next=$("$systemctl" show af-rebuild.timer -p NextElapseUSecRealtime --value 2>/dev/null || true)
    echo "origin/main $(short "$origin")  not deployed yet${next:+ (next check $next)}"
  fi
  if [ -r "$state" ]; then
    jq -r '
      (if .last then
         "last        \(.last.result) \(.last.rev[0:7]) \(.last.subject // "") at \(.last.at)"
         + (if (.last.detail // "") != "" then "\n            \(.last.detail)" else "" end)
       else "last        no deploy recorded yet" end),
      (if .failed then "failed      \(.failed[0:7]), skipped until main moves (af deploy --retry)" else empty end)
    ' "$state"
  else
    echo "last        no deploy recorded yet"
  fi
  # Checked live, not read from state.json: the deploy only writes its flag
  # when it runs, so after a reboot the saved one stays stale until the timer.
  if reboot_pending; then echo "reboot      pending"; else echo "reboot      not needed"; fi
}

# Same test as reboot_pending() in af-deploy.py: the booted kernel, initrd or
# modules differ from the current system's.
reboot_pending() {
  local p
  for p in kernel initrd kernel-modules; do
    [ "$(readlink -f "/run/booted-system/$p")" = "$(readlink -f "/run/current-system/$p")" ] || return 0
  done
  return 1
}

cmd_deploy() {
  local unit=af-rebuild
  case "${1:-}" in
    "") ;;
    --retry) unit=af-rebuild-retry ;;
    *) die "deploy takes no argument but --retry" ;;
  esac
  journalctl -f -n0 -o cat -u "$unit" &
  local follower=$! rc=0
  sudo "$systemctl" start "$unit" || rc=$?
  sleep 1
  kill "$follower" 2>/dev/null || true
  echo
  cmd_status
  return "$rc"
}

cmd_log() {
  journalctl -u af-rebuild -u af-rebuild-retry -u af-rebuild-drill -n "${1:-80}" --no-pager -o short-iso
}

cmd_config() {
  case "${1:-show}" in
    show) jq . "$locals" ;;
    edit)
      sudoedit "$locals"
      jq -e 'type == "object" and has("username") and has("tailnetDomain") and has("sshKeys")' "$locals" >/dev/null \
        || die "$locals is not valid; fix it with 'af config edit' before the next deploy"
      cmd_deploy
      ;;
    *) die "config takes show or edit" ;;
  esac
}

valid_slug() { [[ "$1" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; }

# The list is the `workspace-repos` Secure Note in 1Password (see
# workspace-init.nix). Reading it needs no sign-in: workspace-init keeps a copy.
# Editing it signs in to 1Password as you, since the box's service account
# token is root-only.
repos_sync() {
  local since rc=0
  since=$(date +%s)
  sudo "$systemctl" start workspace-init || rc=$?
  journalctl -u workspace-init --since "@$since" -o cat --no-pager | grep -E '^(workspace-init: |  )' || true
  return "$rc"
}

repos_edit() {
  local action="$1" slug="$2" current new
  op whoami >/dev/null 2>&1 || eval "$(op signin)"
  current=$(op read "$repos_ref")
  case "$action" in
    add)
      if grep -qxF "$slug" <<<"$current"; then
        echo "$slug is already listed"
        return
      fi
      new=$(printf '%s\n%s' "$current" "$slug")
      ;;
    remove)
      grep -qxF "$slug" <<<"$current" || die "$slug is not listed"
      new=$(grep -vxF "$slug" <<<"$current" || true)
      ;;
  esac
  op item edit workspace-repos --vault "Ardent Forge" "notesPlain=$new" >/dev/null
  echo "${action}: $slug"
}

cmd_repos() {
  local sub="${1:-list}" slug="${2:-}"
  case "$sub" in
    list)
      [ -r "$repos_copy" ] || die "no copy of the list yet; run 'af repos sync'"
      grep -v '^[[:space:]]*\(#\|$\)' "$repos_copy" || true
      ;;
    sync) repos_sync ;;
    add)
      valid_slug "$slug" || die "usage: af repos add owner/repo"
      repos_edit add "$slug"
      repos_sync
      ;;
    remove)
      valid_slug "$slug" || die "usage: af repos remove owner/repo"
      repos_edit remove "$slug"
      repos_sync
      echo "its clone in ~/Repos/github.com is left alone"
      ;;
    *) die "repos takes list, sync, add or remove" ;;
  esac
}

cmd_build() {
  local repo out running
  repo=$(checkout)
  echo "building $repo" >&2
  out=$(nix build --no-link --print-out-paths --impure "$repo/nix#nixosConfigurations.$host.config.system.build.toplevel")
  running=$(readlink -f /run/current-system)
  echo "$out"
  if [ "$out" = "$running" ]; then echo "identical to the running system" >&2; fi
}

cmd_update() {
  local repo
  repo=$(checkout)
  nix flake update "$@" --flake "$repo/nix"
  git -C "$repo" diff --stat -- nix/flake.lock
  cmd_build
  echo "review the lock change, then commit and push it to deploy" >&2
}

cmd_pins() {
  local repo
  repo=$(checkout)
  AF_REPO="$repo" python3 "$repo/scripts/pin-check.py" "$@"
}

cmd="${1:-help}"
shift || true
case "$cmd" in
  deploy) cmd_deploy "$@" ;;
  status) cmd_status ;;
  log) cmd_log "$@" ;;
  config) cmd_config "$@" ;;
  repos) cmd_repos "$@" ;;
  build) cmd_build ;;
  update) cmd_update "$@" ;;
  pins) cmd_pins "$@" ;;
  help | -h | --help) usage ;;
  *)
    usage >&2
    exit 2
    ;;
esac
