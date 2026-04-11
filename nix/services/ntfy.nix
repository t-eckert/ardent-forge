# nix/services/ntfy.nix
{ config, pkgs, lib, ... }:

{
  virtualisation.oci-containers.containers.ntfy = {
    image = "binwiederhier/ntfy:latest";
    autoStart = true;

    ports = [
      "127.0.0.1:8090:80"
    ];

    volumes = [
      "/data/ntfy/cache:/var/cache/ntfy"
      "/data/ntfy/etc:/etc/ntfy"
    ];

    cmd = [ "serve" ];

    environment = {
      TZ = "America/Toronto";
    };
  };

  # Ensure data directory exists with correct structure
  systemd.tmpfiles.rules = [
    "d /data/ntfy/cache 0750 root root -"
    "d /data/ntfy/etc 0750 root root -"
  ];

  # NTFY server config — written once, then managed in /data/ntfy/etc/
  environment.etc."ardent-forge/ntfy-server.yml.example".text = ''
    base-url: https://ntfy.ardent-forge.tail1234.ts.net
    cache-file: /var/cache/ntfy/cache.db
    behind-proxy: true
  '';
}
