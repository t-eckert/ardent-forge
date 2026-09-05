# nix/services/ntfy.nix
{ config, pkgs, lib, locals, ... }:

let
  # "ardent-forge.feist-gondola.ts.net" -> "feist-gondola.ts.net". ntfy has its
  # own tsnet node at ntfy.<tailnet>, alongside the cs* apps in caddy.nix.
  tailnet = lib.concatStringsSep "." (builtins.tail (lib.splitString "." locals.tailnetDomain));
in
{
  virtualisation.oci-containers.containers.ntfy = {
    # Pinned by digest for the same reason as the-weather: :latest re-resolves
    # on every start, so the code running here could change across a reboot
    # with nothing in this repo to show for it. It matters more here than
    # there -- this is the path alerts take to a phone, so a silent change
    # breaks the thing that tells you other things broke. Digest as of
    # 2026-09-04 (image built 2026-08-27, ntfy 2.21.0); resolve a new one with
    # `skopeo inspect docker://docker.io/binwiederhier/ntfy:latest`.
    image = "docker.io/binwiederhier/ntfy@sha256:6ef4b819f722fccdc036af611c4774cfdc2de821ab74fdd48bbf4c9d6f8973da";
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

      # iOS cannot hold a background connection to a self-hosted server, so
      # APNs has to be woken by ntfy.sh. On publish this server sends ntfy.sh a
      # poll request only: a message id and a topic derived by hashing
      # base-url + topic. The alert text is not included -- the phone is woken
      # and then fetches the real message from this box over the tailnet.
      #
      # The cost is that this box now makes an outbound call to a third party
      # on every alert, and that alerting depends on ntfy.sh being reachable.
      # Only needed for iOS; Android holds its own connection and needs none
      # of this.
      NTFY_UPSTREAM_BASE_URL = "https://ntfy.sh";
    };
  };

  # Ensure data directory exists with correct structure
  systemd.tmpfiles.rules = [
    "d /data/ntfy/cache 0750 root root -"
    "d /data/ntfy/etc 0750 root root -"
  ];

}
