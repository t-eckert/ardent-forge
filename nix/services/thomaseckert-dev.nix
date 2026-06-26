# nix/services/thomaseckert-dev.nix
{ pkgs, locals, ... }:

{
  systemd.services.thomaseckert-dev = {
    description = "thomaseckert.dev — Astro dev server";
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];
    wantedBy = [ "multi-user.target" ];

    serviceConfig = {
      User = locals.username;
      WorkingDirectory = "/home/${locals.username}/Repos/github.com/t-eckert/thomaseckert.dev/site";
      ExecStart = "${pkgs.nodejs}/bin/npm run dev";
      Restart = "on-failure";
      RestartSec = "5s";
      Environment = [
        "HOME=/home/${locals.username}"
        "PATH=${pkgs.nodejs}/bin:/run/current-system/sw/bin"
      ];
    };
  };
}
