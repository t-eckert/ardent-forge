{
  config,
  pkgs,
  lib,
  dotfiles,
  locals,
  ...
}:

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
    ./services/memory-limits.nix
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
