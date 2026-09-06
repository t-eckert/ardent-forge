{
  config,
  pkgs,
  lib,
  dotfiles,
  locals,
  ...
}:

let
  # Chill Subs + Galley workspace roots, used by the crucible profile below.
  csRoot = "/home/thomaseckert/Projects/Chill-Subs+Galley/Chill-Subs";
  csgSuite = "/home/thomaseckert/Projects/Chill-Subs+Galley/t-eckert/csg/dev-suite";
in
{
  imports = [
    ./services/postgresql.nix
    ./services/monitoring.nix
    ./services/caddy.nix
    ./services/ntfy.nix
    ./services/the-weather.nix
    ./services/notebook-sync.nix
    ./services/marimo.nix
    ./services/lab-sync.nix
    ./services/workspace-init.nix
    ./services/thomaseckert-dev.nix
    ./services/galley-frontend.nix
    ./services/memory-limits.nix
    ./services/crucible.nix
    ./services/smartd.nix
  ];

  # ── System ──────────────────────────────────────────────
  system.stateVersion = "24.11";
  nixpkgs.config.allowUnfree = true;
  nix.settings.experimental-features = [
    "nix-command"
    "flakes"
  ];

  # ── Nix store upkeep ────────────────────────────────────
  # Nothing reclaimed the store before this: it had reached 155GB across 107
  # system generations, more than half the disk in use. Every rebuild adds a
  # generation and each one is a GC root, so old toolchains never leave.
  #
  # 30d of generations is still a long rollback window on a box that is
  # rebuilt by hand, and boot.loader.systemd-boot.configurationLimit keeps the
  # boot menu from growing to match.
  nix.gc = {
    automatic = true;
    dates = "weekly";
    options = "--delete-older-than 30d";
  };

  # Hard-links identical files in the store. Typically reclaims 25-35% and is
  # independent of GC — it deduplicates what is kept rather than deleting.
  nix.optimise = {
    automatic = true;
    dates = [ "03:45" ];
  };

  # ── Boot ────────────────────────────────────────────────
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;
  # Without this the boot menu accumulates an entry per generation — there were
  # 107. GC prunes the store; this prunes what you have to scroll past at boot.
  boot.loader.systemd-boot.configurationLimit = 20;

  # ── Networking ──────────────────────────────────────────
  networking.nftables.enable = true;

  networking = {
    hostName = "ardent-forge";
    interfaces.enp1s0.useDHCP = true;
    nameservers = [
      "1.1.1.1"
      "8.8.8.8"
    ];

    firewall = {
      enable = true;
      # Only allow traffic on Tailscale interface
      trustedInterfaces = [ "tailscale0" ];
      # Allow SSH and DHCP on LAN for initial setup
      allowedTCPPorts = [ 22 ];
      allowedUDPPorts = [ config.services.tailscale.port ];
    };
  };

  # ── Tailscale ───────────────────────────────────────────
  services.tailscale = {
    enable = true;
    useRoutingFeatures = "server";
    extraSetFlags = [ "--ssh" ];
    permitCertUid = "caddy";
  };

  # ── Crucible: containment for workloads that must not touch production ──
  #
  # Left on permanently. A profile costs nothing until something is launched
  # into it, so there is no rebuild-to-toggle dance: the choice is made when you
  # start the work, not when you build the system.
  #
  #   crucible-app chillSubs editor              start one declared app
  #   crucible-shell chillSubs                   drop a shell in (asks for sudo)
  #   crucible-shell chillSubs crucible-verify   prove the shield is real
  #
  # See nix/services/crucible.nix for why enforcement is two layers and why the
  # allowlist is by hostname rather than IP.
  ardentForge.crucible.enable = true;
  ardentForge.crucible.sudoUsers = [ "thomaseckert" ];

  # The Chill Subs + Galley dev suite. Motivated by the 2026-08-10 audit of
  # dev-suite/env, which found the suite holding credentials that reach
  # production: the real AWS bucket with no S3_ENDPOINT, a live SendGrid key,
  # and writable Upstash and Turso. The env overlays neuter those credentials;
  # this profile removes the network capability underneath them, so both layers
  # have to fail together before production is reachable.
  ardentForge.crucible.profiles.chillSubs = {
    description = "Chill Subs + Galley dev suite under adversarial testing";

    # The suite genuinely needs all four: MinIO lives on the tailnet, the
    # databases are rootless-podman port-forwards on loopback, and container-to-
    # container traffic uses podman's CNI nets.
    allowTailnet = true;
    allowPodman = true;
    allowLAN = true;

    # Hostnames, not IPs -- this is the whole reason for the rewrite. The
    # predecessor had to pin Clerk's Cloudflare addresses behind an
    # `allowClerkAuth` flag with a "these rotate, refresh with getent" note, and
    # flip it on and off around every authenticated test. Naming the host
    # instead makes the exception permanent, legible and rotation-proof, and it
    # is *narrower* than the IP list was: an address can be shared by hosts you
    # did not mean to allow, a name cannot.
    allowHosts = [
      "on-elk-6.clerk.accounts.dev" # editor session validation
      "api.clerk.com"
      "binaries.prisma.sh" # prisma generate, on first run
    ];

    # Sized by measurement, not guess: chillest-subs 2045 MB + editor 2019 MB +
    # admin 1042 MB, ~5.1 GB PSS together.
    memoryHigh = "6G";
    memoryMax = "7G";

    environment = {
      HOME = "/home/thomaseckert";
      SUITE_ENV_DIR = "${csgSuite}/env";
      PATH = "/run/wrappers/bin:/etc/profiles/per-user/thomaseckert/bin:/run/current-system/sw/bin:/usr/bin:/bin";
      # System units inherit nothing from environment.d, so the PRISMA paths
      # home.nix exports to the user manager have to be named explicitly here.
      PRISMA_QUERY_ENGINE_LIBRARY = "${pkgs.prisma-engines_6}/lib/libquery_engine.node";
      PRISMA_QUERY_ENGINE_BINARY = "${pkgs.prisma-engines_6}/bin/query-engine";
      PRISMA_SCHEMA_ENGINE_BINARY = "${pkgs.prisma-engines_6}/bin/schema-engine";
      PRISMA_FMT_BINARY = "${pkgs.prisma-engines_6}/bin/prisma-fmt";
    };

    # run-with-env gives the isolated apps exactly the env the process-compose
    # copies get, including the .env.local credential overlays.
    apps = {
      admin = {
        workingDirectory = "${csRoot}/chill-subs/admin";
        command = "${csgSuite}/run-with-env admin -- yarn dev -p 8030 -H 0.0.0.0";
      };
      editor = {
        workingDirectory = "${csRoot}/chill-subs/editor";
        command = "${csgSuite}/run-with-env editor -- yarn dev -p 8010 -H 0.0.0.0";
      };
      chillest-subs = {
        workingDirectory = "${csRoot}/chillest-subs";
        command = "${csgSuite}/run-with-env chillest-subs -- pnpm dev --turbopack -p 8000 -H 0.0.0.0";
      };
    };

    verify = {
      mustReach = [ "http://localhost:8000/" ];
      mustNotReach = [
        "https://s3.amazonaws.com"
        "https://api.sendgrid.com"
        "https://vocal-trout-36239.upstash.io"
        "https://www.chillsubs.com"
      ];
    };
  };

  # ── Time & Locale ──────────────────────────────────────
  time.timeZone = "America/Toronto";
  i18n.defaultLocale = "en_CA.UTF-8";

  # ── Users ───────────────────────────────────────────────
  users.users.${locals.username} = {
    isNormalUser = true;
    extraGroups = [
      "wheel"
      "podman"
    ];
    openssh.authorizedKeys.keys = locals.sshKeys;
    shell = pkgs.zsh;
  };
  # Let Grafana read git-managed dashboard JSON files from the repo
  users.users.grafana.extraGroups = [ "users" ];
  programs.zsh.enable = true;

  # ── SSH ─────────────────────────────────────────────────
  services.openssh = {
    enable = true;
    settings = {
      PasswordAuthentication = false;
      PermitRootLogin = "no";
    };
  };

  # ── Mosh ────────────────────────────────────────────────
  # Roaming terminal sessions that survive sleep and network changes.
  # System-level rather than a home package: this also installs the setgid
  # libutempter wrapper (so sessions show in `who`) and opens UDP 60000-61000.
  # The Tailscale path is already covered by trustedInterfaces; the firewall
  # ports matter for reaching the Forge over LAN.
  programs.mosh.enable = true;

  # ── Podman (for NTFY and The Weather containers) ───────
  virtualisation.podman = {
    enable = true;
    autoPrune.enable = true;
    defaultNetwork.settings.dns_enabled = true;
  };

  # ── nix-ld (run generic Linux binaries, e.g. workerd) ──
  programs.nix-ld.enable = true;
  programs.nix-ld.libraries = with pkgs; [
    stdenv.cc.cc.lib
    zlib
    openssl
    glibc
  ];

  # Workerd (bundled with wrangler) needs this to find CA certs on NixOS
  environment.variables.SSL_CERT_FILE = "/etc/ssl/certs/ca-bundle.crt";

  # ── System packages ────────────────────────────────────
  environment.systemPackages = with pkgs; [
    git
    vim
    curl
    htop
    btop
    _1password-cli
    claude-code
    ghostty.terminfo
    openssl_3
  ];

  # ── Data directories ───────────────────────────────────
  # All persistent data lives under /data/<service>/
  systemd.tmpfiles.rules = [
    "d /data 0755 root root -"
    "d /data/ardent-forge 0750 ${locals.username} users -"
    "d /data/prometheus 0750 prometheus prometheus -"
    "d /data/grafana 0750 grafana grafana -"
    "d /data/loki 0750 loki loki -"
    "d /data/ntfy 0750 root root -"
    "d /data/postgresql 0750 postgres postgres -"
  ];
}
