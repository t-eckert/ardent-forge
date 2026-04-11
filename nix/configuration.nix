{ config, pkgs, lib, dotfiles, locals, ... }:

{
  imports = [
    ./services/ardent-forge.nix
    ./services/postgresql.nix
    ./services/monitoring.nix
    ./services/ollama.nix
    ./services/caddy.nix
    ./services/ntfy.nix
    ./services/the-weather.nix
  ];

  # ── System ──────────────────────────────────────────────
  system.stateVersion = "24.11";
  nixpkgs.config.allowUnfree = true;
  nix.settings.experimental-features = [ "nix-command" "flakes" ];

  # ── Boot ────────────────────────────────────────────────
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  # ── Networking ──────────────────────────────────────────
  networking = {
    hostName = "ardent-forge";
    interfaces.enp1s0.ipv4.addresses = [{
      address = "10.0.0.67";
      prefixLength = 24;
    }];
    defaultGateway = "10.0.0.1";
    nameservers = [ "1.1.1.1" "8.8.8.8" ];

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
  };

  # ── Time & Locale ──────────────────────────────────────
  time.timeZone = "America/Toronto";
  i18n.defaultLocale = "en_CA.UTF-8";

  # ── Users ───────────────────────────────────────────────
  users.users.thomaseckert = {
    isNormalUser = true;
    extraGroups = [ "wheel" "podman" ];
    openssh.authorizedKeys.keys = locals.sshKeys;
    shell = pkgs.zsh;
  };
  programs.zsh.enable = true;

  # ── SSH ─────────────────────────────────────────────────
  services.openssh = {
    enable = true;
    settings = {
      PasswordAuthentication = false;
      PermitRootLogin = "no";
    };
  };

  # ── Podman (for NTFY and The Weather containers) ───────
  virtualisation.podman = {
    enable = true;
    autoPrune.enable = true;
    defaultNetwork.settings.dns_enabled = true;
  };

  # ── System packages ────────────────────────────────────
  environment.systemPackages = with pkgs; [
    git
    vim
    curl
    htop
    _1password-cli
  ];

  # ── Data directories ───────────────────────────────────
  # All persistent data lives under /data/<service>/
  systemd.tmpfiles.rules = [
    "d /data 0755 root root -"
    "d /data/ardent-forge 0750 thomaseckert users -"
    "d /data/ardent-forge/repos 0750 thomaseckert users -"
    "d /data/prometheus 0750 prometheus prometheus -"
    "d /data/grafana 0750 grafana grafana -"
    "d /data/loki 0750 loki loki -"
    "d /data/ntfy 0750 root root -"
    "d /data/postgresql 0750 postgres postgres -"
  ];
}
