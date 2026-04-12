# nix/services/the-weather.nix
{ config, pkgs, lib, ... }:

{
  # The Weather runs as a standalone systemd service with op run
  # rather than a plain OCI container, because it needs 1Password secret injection.
  systemd.services.the-weather = {
    description = "The Weather — local weather data service";
    wantedBy = [ "multi-user.target" ];
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];

    path = [ pkgs._1password-cli pkgs.podman ];

    serviceConfig = {
      Type = "simple";

      # Load 1Password service account token (same one ardent-forge uses)
      EnvironmentFile = "/etc/ardent-forge/op-token";

      ExecStartPre = "${pkgs.podman}/bin/podman pull ghcr.io/t-eckert/the-weather:latest";
      ExecStart = pkgs.writeShellScript "the-weather-start" ''
        exec op run --env-file /data/ardent-forge/the-weather.env -- \
          podman run --rm \
            --name the-weather \
            -p 127.0.0.1:8091:8080 \
            -e OPEN_WEATHER_API_KEY \
            -e HOME_LAT=45.4215 \
            -e HOME_LON=-75.6972 \
            ghcr.io/t-eckert/the-weather:latest
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
