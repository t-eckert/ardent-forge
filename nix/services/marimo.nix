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

      ExecStart = "${pythonEnv}/bin/marimo edit --headless --host 127.0.0.1 --port 2718 --no-token";

      Restart = "on-failure";
      RestartSec = 10;

      NoNewPrivileges = true;
      ProtectSystem = "strict";
      ProtectHome = "read-only";
      ReadWritePaths = [ labDir configDir stateDir uvCacheDir ];
      PrivateTmp = true;
    };
  };

  security.sudo.extraRules = [{
    users = [ locals.username ];
    commands = [
      { command = "/run/current-system/sw/bin/systemctl restart marimo"; options = [ "NOPASSWD" ]; }
      { command = "/run/current-system/sw/bin/systemctl stop marimo"; options = [ "NOPASSWD" ]; }
      { command = "/run/current-system/sw/bin/systemctl start marimo"; options = [ "NOPASSWD" ]; }
    ];
  }];
}
