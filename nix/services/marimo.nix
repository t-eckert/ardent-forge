# nix/services/marimo.nix
{ pkgs, locals, ... }:

let
  home = "/home/${locals.username}";
  labDir = "${home}/Repos/lab";

  # marimo resolves its user config and server state under $HOME. ProtectHome
  # below makes $HOME read-only, so these three have to be punched back out as
  # ReadWritePaths or marimo logs "Read-only file system" on every start and
  # every settings read, and nothing you change in the UI ever persists.
  configDir = "${home}/.config/marimo";
  stateDir = "${home}/.local/state/marimo";

  # Dedicated uv cache. Not ~/.cache/uv: that dir is shared with the user's
  # interactive uv, and handing a sandboxed service write access to it means a
  # notebook can poison the cache the shell uses.
  uvCacheDir = "${home}/.cache/marimo-uv";

  # Where notebooks park cached API responses. Deliberately NOT under labDir:
  # that directory is committed and pushed every 60s by ardent-forge-lab-sync,
  # and third-party API blobs have no business in the repo's history.
  labCacheDir = "${home}/.cache/lab";

  # The interpreter marimo runs notebook cells in. marimo executes cells in
  # its OWN process's Python, not some separately-selected kernel — so a
  # notebook can only import what is in this env. `pkgs.marimo` alone gives
  # you marimo plus its server deps (uvicorn, websockets, pygments) and
  # nothing else, which is why every `import pandas` was failing.
  pythonEnv = pkgs.python3.withPackages (ps: with ps; [
    marimo

    # dataframes / compute
    pandas
    numpy
    polars
    pyarrow
    scipy

    # viz — altair is the one marimo's own dataframe UI elements render with
    altair
    matplotlib
    plotly

    # data access
    duckdb
    sqlalchemy
    psycopg2
    requests
    httpx

    # io
    openpyxl
  ]);

  opBin = "${pkgs._1password-cli}/bin/op";

  # marimo serves --no-token (no auth) and Caddy fronts it for the whole
  # tailnet, and it executes notebook cells in its own process. So marimo's
  # environment is readable by any tailnet device that can open the editor and
  # type os.environ. Putting the vault-wide OP_SERVICE_ACCOUNT_TOKEN there
  # would hand over every secret in "Ardent Forge".
  #
  # This wrapper exists so that exactly one narrow credential survives to exec
  # and nothing else. It uses `op read` rather than `op run` for two reasons:
  # `op run` leaves the service-account token in the child's environment (so a
  # scrubbing shell would be needed anyway), and it stays resident as marimo's
  # parent for the life of the service, holding that token in memory.
  #
  # The PAT is a SEPARATE 1Password item from lab-sync's `github-pat`. That one
  # is a push token — exposing it here would grant any tailnet device write
  # access to every repo, and revoking it to contain a leak would break
  # lab-sync and notebook-sync at the same moment.
  startScript = pkgs.writeShellScript "marimo-start" ''
    # Deliberately no `-e`: a failed secret lookup must not stop marimo from
    # starting. Every other notebook in the lab is unrelated to GitHub.
    set -uo pipefail

    github_token=""

    if [ -n "''${OP_SERVICE_ACCOUNT_TOKEN:-}" ]; then
      for _attempt in 1 2 3; do
        # `op` needs a WRITABLE config dir — it creates an op-daemon.sock
        # there. ProtectHome=read-only makes $HOME/.config read-only, so
        # without --config this fails with "cannot create directory" before it
        # ever reaches the network. RuntimeDirectory is the one writable spot
        # ProtectSystem=strict leaves, and systemd tears it down on stop.
        github_token="$(
          HOME="$RUNTIME_DIRECTORY" ${opBin} --config "$RUNTIME_DIRECTORY/op" \
            read --no-newline "op://Ardent Forge/github-pat-marimo/credential"
        )" && [ -n "$github_token" ] && break
        github_token=""
        # DNS can lag network-online.target on the first boot pass.
        ${pkgs.coreutils}/bin/sleep 5
      done
    fi

    if [ -n "$github_token" ]; then
      export GITHUB_TOKEN="$github_token"
    else
      echo "marimo: no GitHub PAT resolved from 1Password; starting without GITHUB_TOKEN" >&2
    fi
    unset github_token

    # THE POINT OF THIS FILE. Everything above runs so that this line can.
    unset OP_SERVICE_ACCOUNT_TOKEN

    exec ${pythonEnv}/bin/marimo edit --headless --host 127.0.0.1 --port 2718 --no-token
  '';
in {
  # These must exist BEFORE the service's mount namespace is set up.
  # ReadWritePaths bind-mounts each path at namespace-setup time, which happens
  # before ExecStartPre — and a missing ReadWritePath makes the unit fail to
  # start outright. ProtectHome=read-only would block creating them from inside
  # the sandbox anyway. tmpfiles runs outside the sandbox, so it can.
  systemd.tmpfiles.rules = [
    "d ${labDir} 0755 ${locals.username} users -"
    "d ${configDir} 0755 ${locals.username} users -"
    "d ${stateDir} 0755 ${locals.username} users -"
    "d ${uvCacheDir} 0755 ${locals.username} users -"
    "d ${labCacheDir} 0700 ${locals.username} users -"
  ];

  # Put the same env on the interactive PATH, so `marimo edit`, `marimo convert`
  # and `marimo export` in a shell are the exact interpreter the server runs.
  # Sharing one derivation is the point — a separately-declared user-level
  # marimo would drift from the service's package set and "works in the CLI,
  # fails in the browser" would follow.
  environment.systemPackages = [ pythonEnv ];

  systemd.services.marimo = {
    description = "Marimo — interactive Python notebooks (lab.*)";
    wantedBy = [ "multi-user.target" ];
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];

    # uv backs marimo's per-notebook sandbox mode (PEP 723 inline deps).
    # git is here because marimo shells out to it for the notebook file history.
    path = [ pkgs.uv pkgs.git ];

    environment = {
      UV_CACHE_DIR = uvCacheDir;

      # On NixOS a uv-downloaded CPython is dynamically linked against paths
      # that don't exist and won't run. Force uv to reuse the store interpreter
      # rather than fetching its own when it resolves a sandboxed notebook.
      UV_PYTHON = "${pythonEnv}/bin/python3";
      UV_PYTHON_DOWNLOADS = "never";

      LAB_CACHE_DIR = labCacheDir;
    };

    serviceConfig = {
      Type = "simple";
      User = locals.username;
      Group = "users";
      WorkingDirectory = labDir;

      ExecStartPre = pkgs.writeShellScript "marimo-pre" ''
        mkdir -p ${labDir}
        if [ ! -d ${labDir}/.git ]; then
          ${pkgs.git}/bin/git -C ${labDir} init
        fi
      '';

      ExecStart = "${startScript}";

      # Read by PID 1 before the drop to User=, so the root-only 0400 token
      # file works. The leading '-' makes a missing file non-fatal: without it,
      # no token file means no marimo at all, and every notebook goes dark
      # rather than just the GitHub one.
      EnvironmentFile = "-/etc/ardent-forge/op-token";

      # Writable tmpfs for `op`'s config and daemon socket — see startScript.
      RuntimeDirectory = "marimo";
      RuntimeDirectoryMode = "0700";

      Restart = "on-failure";
      RestartSec = 10;

      NoNewPrivileges = true;
      ProtectSystem = "strict";
      ProtectHome = "read-only";
      ReadWritePaths = [ labDir configDir stateDir uvCacheDir labCacheDir ];
      PrivateTmp = true;
    };
  };

  # Env template — secret resolved by the startScript above, not `op run`.
  # Listed for parity with the-weather.nix and lab-sync.nix so every op:// URI
  # this box depends on is discoverable from /etc.
  environment.etc."ardent-forge/marimo.env.example".text = ''
    GITHUB_TOKEN=op://Ardent Forge/github-pat-marimo/credential
  '';

  security.sudo.extraRules = [{
    users = [ locals.username ];
    commands = [
      { command = "/run/current-system/sw/bin/systemctl restart marimo"; options = [ "NOPASSWD" ]; }
      { command = "/run/current-system/sw/bin/systemctl stop marimo"; options = [ "NOPASSWD" ]; }
      { command = "/run/current-system/sw/bin/systemctl start marimo"; options = [ "NOPASSWD" ]; }
    ];
  }];
}
