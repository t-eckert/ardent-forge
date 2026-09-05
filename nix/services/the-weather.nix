# nix/services/the-weather.nix
{ config, pkgs, lib, ... }:

let
  # Pinned by digest rather than :latest. The old form re-resolved the tag on
  # every start, so the code running here could change across a reboot with no
  # corresponding change in this repo -- the same drift an unpinned flake input
  # would cause, and invisible in exactly the same way. Digest as of
  # 2026-09-04; bump it deliberately to take a new build.
  image = "ghcr.io/t-eckert/the-weather@sha256:149423183d3584dab08923b8b6b293b640622e70bce7a7c2d1489b4ef6601ec9";
in
{
  # The Weather runs as a standalone systemd service with op run
  # rather than a plain OCI container, because it needs 1Password secret injection.
  systemd.services.the-weather = {
    description = "The Weather — local weather data service";
    wantedBy = [ "multi-user.target" ];
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];

    path = [ pkgs._1password-cli pkgs.podman ];

    environment = {
      HOME = "/root";
    };

    serviceConfig = {
      Type = "simple";

      # Load 1Password service account token (same one ardent-forge uses)
      EnvironmentFile = "/etc/ardent-forge/op-token";

      # Leading "-" so a pull failure is not fatal. With a digest pin the local
      # copy is by definition the same image, so an unreachable or rate-limited
      # ghcr.io should not stop a service that already has what it needs. It
      # used to: the pull was required, so the registry was a hard dependency
      # of starting up.
      ExecStartPre = "-${pkgs.podman}/bin/podman pull ${image}";
      ExecStart = pkgs.writeShellScript "the-weather-start" ''
        exec op run --env-file /data/ardent-forge/the-weather.env -- \
          podman run --rm \
            --name the-weather \
            -p 127.0.0.1:8091:8080 \
            -e OPEN_WEATHER_API_KEY \
            -e HOME_LAT=45.4215 \
            -e HOME_LON=-75.6972 \
            ${image}
      '';
      ExecStop = "${pkgs.podman}/bin/podman stop the-weather";

      Restart = "on-failure";
      RestartSec = 30;
    };
  };

  # 1Password env file reference (no secrets, just op:// URIs)
  environment.etc."ardent-forge/the-weather.env.example".text = ''
    OPEN_WEATHER_API_KEY=op://Ardent Forge/open-weather-api-key/credential
  '';
}
