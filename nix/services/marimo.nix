# nix/services/marimo.nix
{ pkgs, locals, ... }:

let
  labDir = "/home/${locals.username}/Repos/lab";
in {
  # Ensure the lab dir exists BEFORE the service's mount namespace is set up.
  # ReadWritePaths/WorkingDirectory bind-mount labDir at namespace-setup time,
  # which happens before ExecStartPre — and ProtectHome=read-only would block
  # creating it inside the sandbox anyway. tmpfiles runs outside the sandbox.
  systemd.tmpfiles.rules = [
    "d ${labDir} 0755 ${locals.username} users -"
  ];

  systemd.services.marimo = {
    description = "Marimo — interactive Python notebooks (lab.*)";
    wantedBy = [ "multi-user.target" ];
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];

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

      ExecStart = "${pkgs.marimo}/bin/marimo edit --headless --host 127.0.0.1 --port 2718 --no-token";

      Restart = "on-failure";
      RestartSec = 10;

      NoNewPrivileges = true;
      ProtectSystem = "strict";
      ProtectHome = "read-only";
      ReadWritePaths = [ labDir ];
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
