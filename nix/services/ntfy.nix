# nix/services/ntfy.nix
{ config, pkgs, lib, locals, ... }:

let
  # "ardent-forge.feist-gondola.ts.net" -> "feist-gondola.ts.net". ntfy has its
  # own tsnet node at ntfy.<tailnet>, alongside the cs* apps in caddy.nix.
  tailnet = lib.concatStringsSep "." (builtins.tail (lib.splitString "." locals.tailnetDomain));
in
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

      # Configured by environment rather than through the mounted
      # /data/ntfy/etc, which was never populated -- ntfy has been running on
      # defaults this whole time, reporting base_url "" and app_root "/". That
      # is what broke the web app when it was served under a path prefix, and
      # so why nothing was ever subscribed to receive an alert. Environment
      # beats the config file in ntfy's precedence, so this holds whatever that
      # directory does or does not contain.
      #
      # Note the host: ntfy.<tailnet>, not ntfy.<tailnetDomain>. The old
      # example config used the latter, which has an extra label and matches no
      # node -- part of why that subdomain never served a request.
      NTFY_BASE_URL = "https://ntfy.${tailnet}";
      NTFY_BEHIND_PROXY = "true";
      NTFY_CACHE_FILE = "/var/cache/ntfy/cache.db";
    };
  };

  # Ensure data directory exists with correct structure
  systemd.tmpfiles.rules = [
    "d /data/ntfy/cache 0750 root root -"
    "d /data/ntfy/etc 0750 root root -"
  ];

}
