# NixOS Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a complete NixOS configuration for the Bee Link mini PC that runs Ardent Forge as a systemd service alongside PostgreSQL, monitoring (Prometheus/Grafana/Loki), Ollama, NTFY, The Weather, Caddy, and Tailscale — with the user's full dev environment available over SSH.

**Architecture:** A NixOS flake in the ardent-forge repo (`nix/`) declares the entire system. Services that have native NixOS modules (PostgreSQL, Prometheus, Grafana, Tailscale, Caddy, Ollama) use them directly. NTFY and The Weather run as Podman containers managed by systemd. Ardent Forge runs as a systemd service using uv to manage its Python environment. 1Password CLI injects secrets at service start via `op run`. The dotfiles repo is a flake input for home-manager so the user gets their full dev environment when SSH'd in.

**Tech Stack:** NixOS, Nix flakes, systemd, Podman, Caddy, Tailscale, 1Password CLI, home-manager

**Hardware:** Bee Link mini PC — Intel N150, 16GB RAM, 1TB NVMe, no GPU. Static local IP 10.0.0.67.

---

## File Structure

```
ardent-forge/
└── nix/
    ├── flake.nix                  # System flake — inputs, nixosConfiguration output
    ├── flake.lock                 # Auto-generated lock file
    ├── configuration.nix          # Main system config — imports all modules, base packages
    ├── hardware.nix               # Bee Link hardware config (generated on first boot, placeholder for now)
    ├── services/
    │   ├── ardent-forge.nix       # Ardent Forge systemd service + uv environment
    │   ├── postgresql.nix         # PostgreSQL 17, tuned for N150/16GB
    │   ├── monitoring.nix         # Prometheus + Grafana + Loki
    │   ├── ollama.nix             # Ollama local model serving
    │   ├── caddy.nix              # Caddy reverse proxy for all HTTP services
    │   ├── ntfy.nix               # NTFY as Podman container
    │   └── the-weather.nix        # The Weather as Podman container
    └── home.nix                   # Home-manager config for thomaseckert (imports dotfiles)
```

---

### Task 1: Flake & Base System Configuration

**Files:**
- Create: `nix/flake.nix`
- Create: `nix/configuration.nix`
- Create: `nix/hardware.nix`

This task sets up the NixOS flake with all inputs, the base system configuration (locale, timezone, users, firewall, SSH), and a placeholder hardware config. The hardware config will be regenerated on the actual machine during installation.

- [ ] **Step 1: Create the flake**

```nix
# nix/flake.nix
{
  description = "Ardent Forge — NixOS configuration for Bee Link";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Thomas's dotfiles for dev environment
    dotfiles = {
      url = "github:t-eckert/dotfiles";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, home-manager, dotfiles }: {
    nixosConfigurations.ardent-forge = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      specialArgs = { inherit dotfiles; };
      modules = [
        ./hardware.nix
        ./configuration.nix
        home-manager.nixosModules.home-manager
        {
          home-manager = {
            useGlobalPkgs = true;
            useUserPackages = true;
            extraSpecialArgs = {
              inherit dotfiles;
              isDarwin = false;
              isLinux = true;
            };
            users.thomaseckert = import ./home.nix;
          };
        }
      ];
    };
  };
}
```

- [ ] **Step 2: Create the base system configuration**

```nix
# nix/configuration.nix
{ config, pkgs, lib, dotfiles, ... }:

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
    interfaces.eno1.ipv4.addresses = [{
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
    openssh.authorizedKeys.keys = [
      # 1Password SSH agent keys — add your public key here
      "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIK+example thomaseckert"
    ];
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
```

- [ ] **Step 3: Create placeholder hardware config**

This file is regenerated on the real machine with `nixos-generate-config`. This placeholder lets the flake evaluate.

```nix
# nix/hardware.nix
# Placeholder — regenerate on the Bee Link with:
#   nixos-generate-config --show-hardware-config > nix/hardware.nix
{ config, lib, pkgs, modulesPath, ... }:

{
  imports = [
    (modulesPath + "/installer/scan/not-detected.nix")
  ];

  boot.initrd.availableKernelModules = [ "xhci_pci" "ahci" "nvme" "usbhid" "sd_mod" ];
  boot.kernelModules = [ "kvm-intel" ];

  fileSystems."/" = {
    device = "/dev/disk/by-label/nixos";
    fsType = "ext4";
  };

  fileSystems."/boot" = {
    device = "/dev/disk/by-label/boot";
    fsType = "vfat";
    options = [ "fmask=0022" "dmask=0022" ];
  };

  swapDevices = [
    { device = "/dev/disk/by-label/swap"; }
  ];

  hardware.cpu.intel.updateMicrocode = true;
  nixpkgs.hostPlatform = "x86_64-linux";
}
```

- [ ] **Step 4: Commit**

```bash
git add nix/flake.nix nix/configuration.nix nix/hardware.nix
git commit -m "feat(nix): add flake and base system configuration

NixOS flake with nixpkgs, home-manager, and dotfiles inputs.
Base config: Tailscale networking, SSH, Podman, data directories."
```

---

### Task 2: Ardent Forge systemd Service

**Files:**
- Create: `nix/services/ardent-forge.nix`

The main application runs as a systemd service under the `thomaseckert` user. It uses `op run` to inject secrets from 1Password at startup, and `uv` to manage the Python environment from the repo checkout.

- [ ] **Step 1: Create the service module**

```nix
# nix/services/ardent-forge.nix
{ config, pkgs, lib, ... }:

let
  forgeDir = "/data/ardent-forge";
  repoDir = "${forgeDir}/repo";
in {
  systemd.services.ardent-forge = {
    description = "Ardent Forge — agentic development platform";
    wantedBy = [ "multi-user.target" ];
    after = [ "network-online.target" "postgresql.service" "tailscaled.service" ];
    wants = [ "network-online.target" ];
    requires = [ "postgresql.service" ];

    path = with pkgs; [
      git
      gh
      _1password-cli
      nodejs_22  # for Claude Code CLI
      uv
    ];

    environment = {
      FORGE_DB_PATH = "${forgeDir}/forge.db";
      FORGE_WORKSPACE_DIR = "${forgeDir}/repos";
      FORGE_HOST = "127.0.0.1";
      FORGE_PORT = "7030";
      HOME = "/home/thomaseckert";
    };

    serviceConfig = {
      Type = "simple";
      User = "thomaseckert";
      Group = "users";
      WorkingDirectory = repoDir;

      # 1Password injects secrets as env vars
      # Requires: `op signin` done once interactively as thomaseckert
      ExecStart = pkgs.writeShellScript "ardent-forge-start" ''
        exec ${pkgs._1password-cli}/bin/op run \
          --env-file ${forgeDir}/forge.env \
          -- ${pkgs.uv}/bin/uv run forge
      '';

      Restart = "on-failure";
      RestartSec = 10;

      # Hardening
      NoNewPrivileges = true;
      ProtectSystem = "strict";
      ProtectHome = "read-only";
      ReadWritePaths = [
        forgeDir
        "/home/thomaseckert"
      ];
      PrivateTmp = true;
    };
  };

  # The 1Password env file maps op:// URIs to env var names.
  # This file contains NO secrets — only references.
  environment.etc."ardent-forge/forge.env.example".text = ''
    FORGE_ANTHROPIC_API_KEY=op://ArdentForge/anthropic-api-key/credential
    FORGE_GITHUB_TOKEN=op://ArdentForge/github-pat/credential
    FORGE_LINEAR_API_KEY=op://ArdentForge/linear-api-key/credential
    FORGE_LINEAR_TEAM_ID=op://ArdentForge/linear-team-id/credential
  '';
}
```

- [ ] **Step 2: Commit**

```bash
git add nix/services/ardent-forge.nix
git commit -m "feat(nix): add ardent-forge systemd service

Runs under thomaseckert user, uses op run for secrets injection,
uv for Python environment management."
```

---

### Task 3: PostgreSQL Service

**Files:**
- Create: `nix/services/postgresql.nix`

Native NixOS PostgreSQL module, tuned for the Bee Link hardware (Intel N150, 16GB RAM, NVMe SSD). The existing K8s config had detailed tuning we'll carry over.

- [ ] **Step 1: Create the PostgreSQL module**

```nix
# nix/services/postgresql.nix
{ config, pkgs, lib, ... }:

{
  services.postgresql = {
    enable = true;
    package = pkgs.postgresql_17;
    dataDir = "/data/postgresql";

    enableTCPIP = true;

    # Only allow connections from Tailscale and localhost
    authentication = pkgs.lib.mkForce ''
      # TYPE  DATABASE        USER            ADDRESS                 METHOD
      local   all             all                                     peer
      host    all             all             127.0.0.1/32            scram-sha-256
      host    all             all             100.64.0.0/10           scram-sha-256
    '';

    settings = {
      # ── Memory (tuned for 16GB RAM, shared with other services) ──
      shared_buffers = "2GB";
      effective_cache_size = "12GB";
      maintenance_work_mem = "512MB";
      work_mem = "32MB";

      # ── Connections ──
      max_connections = 200;
      max_worker_processes = 4;

      # ── WAL ──
      max_wal_size = "4GB";
      wal_compression = "on";
      checkpoint_timeout = "10min";

      # ── Autovacuum (SSD-optimized) ──
      autovacuum_vacuum_cost_delay = "2ms";
      autovacuum_vacuum_cost_limit = 2000;

      # ── Logging ──
      log_min_duration_statement = 1000;  # Log queries > 1s
    };

    # Create databases for services
    ensureDatabases = [
      "ardent_forge"
      "grafana"
    ];

    ensureUsers = [
      {
        name = "ardent_forge";
        ensureDBOwnership = true;
      }
      {
        name = "grafana";
        ensureDBOwnership = true;
      }
    ];
  };

  # Postgres exporter for Prometheus
  services.prometheus.exporters.postgres = {
    enable = true;
    port = 9187;
    runAsLocalSuperUser = true;
  };
}
```

- [ ] **Step 2: Commit**

```bash
git add nix/services/postgresql.nix
git commit -m "feat(nix): add PostgreSQL service tuned for Bee Link

PostgreSQL 17 with N150/16GB tuning, Tailscale auth,
databases for ardent_forge and grafana, prometheus exporter."
```

---

### Task 4: Monitoring Stack (Prometheus + Grafana + Loki)

**Files:**
- Create: `nix/services/monitoring.nix`

All three monitoring services use native NixOS modules. Prometheus scrapes node metrics and the postgres exporter. Grafana has Prometheus and Loki as datasources. Loki collects logs from systemd journal.

- [ ] **Step 1: Create the monitoring module**

```nix
# nix/services/monitoring.nix
{ config, pkgs, lib, ... }:

{
  # ── Prometheus ──────────────────────────────────────────
  services.prometheus = {
    enable = true;
    port = 9090;
    stateDir = "prometheus";  # Relative to /var/lib/

    retentionTime = "30d";

    globalConfig = {
      scrape_interval = "15s";
      evaluation_interval = "15s";
    };

    scrapeConfigs = [
      {
        job_name = "node";
        static_configs = [{
          targets = [ "127.0.0.1:${toString config.services.prometheus.exporters.node.port}" ];
        }];
      }
      {
        job_name = "postgres";
        static_configs = [{
          targets = [ "127.0.0.1:9187" ];
        }];
      }
      {
        job_name = "ardent-forge";
        static_configs = [{
          targets = [ "127.0.0.1:7030" ];
        }];
        metrics_path = "/metrics";
      }
      {
        job_name = "loki";
        static_configs = [{
          targets = [ "127.0.0.1:3100" ];
        }];
      }
    ];
  };

  # Node exporter for system metrics
  services.prometheus.exporters.node = {
    enable = true;
    port = 9100;
    enabledCollectors = [
      "cpu" "diskstats" "filesystem" "loadavg"
      "meminfo" "netdev" "stat" "time" "vmstat"
    ];
  };

  # ── Grafana ─────────────────────────────────────────────
  services.grafana = {
    enable = true;
    dataDir = "/data/grafana";

    settings = {
      server = {
        http_addr = "127.0.0.1";
        http_port = 3000;
        root_url = "https://grafana.ardent-forge.tail1234.ts.net";
      };
      security = {
        admin_user = "admin";
        # Set on first boot, then managed in Grafana UI
        admin_password = "$__env{GRAFANA_ADMIN_PASSWORD}";
      };
      database = {
        type = "postgres";
        host = "/run/postgresql";
        name = "grafana";
        user = "grafana";
      };
      analytics.reporting_enabled = false;
    };

    provision = {
      datasources.settings.datasources = [
        {
          name = "Prometheus";
          type = "prometheus";
          url = "http://127.0.0.1:9090";
          isDefault = true;
        }
        {
          name = "Loki";
          type = "loki";
          url = "http://127.0.0.1:3100";
        }
      ];
    };
  };

  # ── Loki ────────────────────────────────────────────────
  services.loki = {
    enable = true;
    dataDir = "/data/loki";

    configuration = {
      auth_enabled = false;

      server = {
        http_listen_port = 3100;
        grpc_listen_port = 9096;
      };

      common = {
        path_prefix = "/data/loki";
        replication_factor = 1;
        ring.kvstore.store = "inmemory";
        ring.instance_addr = "127.0.0.1";
      };

      schema_config.configs = [{
        from = "2024-01-01";
        store = "tsdb";
        object_store = "filesystem";
        schema = "v13";
        index = {
          prefix = "index_";
          period = "24h";
        };
      }];

      storage_config.filesystem.directory = "/data/loki/chunks";

      limits_config = {
        ingestion_rate_mb = 10;
        ingestion_burst_size_mb = 20;
      };

      compactor = {
        working_directory = "/data/loki/compactor";
        compaction_interval = "10m";
      };
    };
  };

  # Promtail — ships systemd journal logs to Loki
  services.promtail = {
    enable = true;
    configuration = {
      server = {
        http_listen_port = 9080;
        grpc_listen_port = 0;
      };

      positions.filename = "/var/lib/promtail/positions.yaml";

      clients = [{
        url = "http://127.0.0.1:3100/loki/api/v1/push";
      }];

      scrape_configs = [{
        job_name = "journal";
        journal = {
          max_age = "12h";
          labels = {
            job = "systemd-journal";
            host = "ardent-forge";
          };
        };
        relabel_configs = [{
          source_labels = [ "__journal__systemd_unit" ];
          target_label = "unit";
        }];
      }];
    };
  };
}
```

- [ ] **Step 2: Commit**

```bash
git add nix/services/monitoring.nix
git commit -m "feat(nix): add monitoring stack (Prometheus, Grafana, Loki)

Prometheus scrapes node, postgres, loki, and ardent-forge.
Grafana uses PostgreSQL backend with provisioned datasources.
Loki with Promtail collecting systemd journal logs."
```

---

### Task 5: Ollama Service

**Files:**
- Create: `nix/services/ollama.nix`

Ollama serves local small models for task triage. The Bee Link has no GPU, so this runs CPU-only. A oneshot service pulls the default model after Ollama starts.

- [ ] **Step 1: Create the Ollama module**

```nix
# nix/services/ollama.nix
{ config, pkgs, lib, ... }:

{
  services.ollama = {
    enable = true;
    listenAddress = "127.0.0.1:11434";

    # CPU-only — no GPU on the Bee Link
    acceleration = false;

    # Models stored in default location /var/lib/ollama
  };

  # Pull a small, fast model after Ollama starts
  systemd.services.ollama-model-pull = {
    description = "Pull default Ollama model for task triage";
    wantedBy = [ "multi-user.target" ];
    after = [ "ollama.service" ];
    requires = [ "ollama.service" ];

    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      ExecStart = "${pkgs.ollama}/bin/ollama pull qwen2.5:3b";
    };
  };
}
```

- [ ] **Step 2: Commit**

```bash
git add nix/services/ollama.nix
git commit -m "feat(nix): add Ollama service for local model triage

CPU-only, listens on localhost:11434, pulls qwen2.5:3b on first boot."
```

---

### Task 6: Caddy Reverse Proxy

**Files:**
- Create: `nix/services/caddy.nix`

Caddy sits in front of all HTTP services. Since everything is Tailscale-only, Caddy handles routing by hostname. Tailscale's HTTPS certificates are used via `tailscale cert` integration.

- [ ] **Step 1: Create the Caddy module**

```nix
# nix/services/caddy.nix
{ config, pkgs, lib, ... }:

let
  # Replace with your actual tailnet hostname after `tailscale up`
  tsHostname = "ardent-forge";
  tsDomain = "${tsHostname}.tail1234.ts.net";
in {
  services.caddy = {
    enable = true;

    # Caddy serves all HTTP services behind Tailscale
    virtualHosts = {
      # Ardent Forge UI + API
      "https://${tsDomain}" = {
        extraConfig = ''
          reverse_proxy 127.0.0.1:7030
        '';
      };

      # Grafana
      "https://grafana.${tsDomain}" = {
        extraConfig = ''
          reverse_proxy 127.0.0.1:3000
        '';
      };

      # Prometheus (direct access for debugging)
      "https://prometheus.${tsDomain}" = {
        extraConfig = ''
          reverse_proxy 127.0.0.1:9090
        '';
      };

      # NTFY
      "https://ntfy.${tsDomain}" = {
        extraConfig = ''
          reverse_proxy 127.0.0.1:8090
        '';
      };
    };
  };

  # Allow Caddy to read Tailscale certs
  systemd.services.caddy.serviceConfig.EnvironmentFile = "";
  users.users.caddy.extraGroups = [ "tailscale-cert" ];
}
```

- [ ] **Step 2: Commit**

```bash
git add nix/services/caddy.nix
git commit -m "feat(nix): add Caddy reverse proxy for Tailscale HTTPS

Routes: ardent-forge UI/API, grafana, prometheus, ntfy.
All services accessible only over tailnet."
```

---

### Task 7: NTFY Container

**Files:**
- Create: `nix/services/ntfy.nix`

NTFY runs as a Podman container managed by systemd. Used by Ardent Forge to send notifications.

- [ ] **Step 1: Create the NTFY module**

```nix
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
```

- [ ] **Step 2: Commit**

```bash
git add nix/services/ntfy.nix
git commit -m "feat(nix): add NTFY container for agent notifications

Podman container on port 8090, persistent cache at /data/ntfy/."
```

---

### Task 8: The Weather Container

**Files:**
- Create: `nix/services/the-weather.nix`

The Weather is a custom Go service that provides local weather data. Runs as a Podman container. The API key is injected via 1Password.

- [ ] **Step 1: Create The Weather module**

```nix
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
    OPEN_WEATHER_API_KEY=op://ArdentForge/open-weather-api-key/credential
  '';
}
```

- [ ] **Step 2: Commit**

```bash
git add nix/services/the-weather.nix
git commit -m "feat(nix): add The Weather container for local weather data

Podman container with 1Password secret injection, Ottawa coordinates."
```

---

### Task 9: Home Manager / Dev Environment

**Files:**
- Create: `nix/home.nix`

This imports the dev environment from the dotfiles repo so SSH sessions have the full toolset (Neovim, Zsh, Git, Go, Node, etc.). It references the existing linux home-manager config from dotfiles and adds Ardent Forge-specific extras.

- [ ] **Step 1: Create the home-manager module**

```nix
# nix/home.nix
{ config, pkgs, lib, dotfiles, ... }:

{
  imports = [
    # Import the Linux home config from dotfiles
    # This brings in: zsh, git, neovim, starship, and core packages
    "${dotfiles}/nix/linux/default.nix"
  ];

  home = {
    username = "thomaseckert";
    homeDirectory = "/home/thomaseckert";
    stateVersion = "24.05";
  };

  # Ardent Forge-specific additions on top of dotfiles
  home.packages = with pkgs; [
    # Python tooling for Ardent Forge development
    uv
    python313

    # Container management
    podman

    # Claude Code CLI (installed via npm)
    # Run: npm install -g @anthropic-ai/claude-code
    # after first login

    # Monitoring tools
    prometheus
    grafana-loki
  ];

  # Environment variables for dev work
  home.sessionVariables = {
    FORGE_DB_PATH = "/data/ardent-forge/forge.db";
    FORGE_WORKSPACE_DIR = "/data/ardent-forge/repos";
  };

  # Git config — clone the ardent-forge repo on first setup
  home.file.".local/bin/forge-setup" = {
    executable = true;
    text = ''
      #!/usr/bin/env bash
      set -euo pipefail

      REPO_DIR="/data/ardent-forge/repo"
      if [ ! -d "$REPO_DIR/.git" ]; then
        echo "Cloning ardent-forge repo..."
        git clone https://github.com/t-eckert/ardent-forge.git "$REPO_DIR"
        cd "$REPO_DIR"
        uv sync
        echo "Done. Repo at $REPO_DIR, venv ready."
      else
        echo "Repo already exists at $REPO_DIR"
      fi

      # Create 1Password env files from examples
      for f in /etc/ardent-forge/*.env.example; do
        target="/data/ardent-forge/$(basename "$f" .example)"
        if [ ! -f "$target" ]; then
          cp "$f" "$target"
          echo "Created $target from example — edit op:// URIs if needed"
        fi
      done

      echo "Setup complete. Run: sudo systemctl start ardent-forge"
    '';
  };
}
```

- [ ] **Step 2: Commit**

```bash
git add nix/home.nix
git commit -m "feat(nix): add home-manager config for dev environment

Imports dotfiles linux config, adds Python/uv/Podman,
includes first-boot setup script."
```

---

### Task 10: Installation Runbook

**Files:**
- Create: `docs/installation.md`

This is the step-by-step guide for installing NixOS on the Bee Link and deploying the configuration. It's a runbook, not automation — the physical installation requires hands-on steps.

- [ ] **Step 1: Write the installation runbook**

```markdown
# Ardent Forge — NixOS Installation Runbook

## Prerequisites

- Bee Link mini PC (Intel N150, 16GB RAM, 1TB NVMe)
- USB drive (8GB+)
- Monitor + keyboard (for initial install only)
- 1Password account with "ArdentForge" vault containing:
  - `anthropic-api-key`
  - `github-pat`
  - `linear-api-key`
  - `linear-team-id`
  - `open-weather-api-key`

## Phase 1: Create NixOS USB Installer

On your Mac:

    # Download minimal NixOS ISO (x86_64)
    curl -LO https://channels.nixos.org/nixos-unstable/latest-nixos-minimal-x86_64-linux.iso

    # Find USB device
    diskutil list

    # Write ISO (replace diskN with your USB)
    sudo dd if=latest-nixos-minimal-x86_64-linux.iso of=/dev/rdiskN bs=4m status=progress
    diskutil eject /dev/diskN

## Phase 2: Install NixOS on Bee Link

Boot from USB, then:

    # Connect to network (ethernet should auto-configure)
    ip a

    # Partition the NVMe
    sudo parted /dev/nvme0n1 -- mklabel gpt
    sudo parted /dev/nvme0n1 -- mkpart ESP fat32 1MB 1GB
    sudo parted /dev/nvme0n1 -- set 1 esp on
    sudo parted /dev/nvme0n1 -- mkpart primary 1GB -8GB
    sudo parted /dev/nvme0n1 -- mkpart primary linux-swap -8GB 100%

    # Format
    sudo mkfs.fat -F 32 -n boot /dev/nvme0n1p1
    sudo mkfs.ext4 -L nixos /dev/nvme0n1p2
    sudo mkswap -L swap /dev/nvme0n1p3

    # Mount
    sudo mount /dev/disk/by-label/nixos /mnt
    sudo mkdir -p /mnt/boot
    sudo mount /dev/disk/by-label/boot /mnt/boot

    # Generate hardware config
    sudo nixos-generate-config --root /mnt

    # Copy the generated hardware config — you'll want this
    cat /mnt/etc/nixos/hardware-configuration.nix

    # Minimal bootstrap config to get SSH + flakes working
    cat > /mnt/etc/nixos/configuration.nix << 'NIXEOF'
    { config, pkgs, ... }:
    {
      imports = [ ./hardware-configuration.nix ];
      boot.loader.systemd-boot.enable = true;
      boot.loader.efi.canTouchEfiVariables = true;
      networking.hostName = "ardent-forge";
      time.timeZone = "America/Toronto";
      services.openssh.enable = true;
      users.users.thomaseckert = {
        isNormalUser = true;
        extraGroups = [ "wheel" ];
        openssh.authorizedKeys.keys = [
          "ssh-ed25519 AAAAC3... thomaseckert"
        ];
      };
      nix.settings.experimental-features = [ "nix-command" "flakes" ];
      environment.systemPackages = with pkgs; [ git vim curl ];
      system.stateVersion = "24.11";
    }
    NIXEOF

    # Install
    sudo nixos-install

    # Set root password when prompted, then reboot
    sudo reboot

## Phase 3: Deploy Full Configuration

From your Mac, after the Bee Link has rebooted and you can SSH in:

    # SSH to the Bee Link (via local network first time)
    ssh thomaseckert@10.0.0.67

    # On the Bee Link: clone the ardent-forge repo
    git clone https://github.com/t-eckert/ardent-forge.git /data/ardent-forge/repo
    cd /data/ardent-forge/repo

    # Copy the real hardware config from the bootstrap install
    cp /etc/nixos/hardware-configuration.nix nix/hardware.nix

    # Apply the full NixOS configuration
    sudo nixos-rebuild switch --flake ./nix#ardent-forge

    # Set up Tailscale
    sudo tailscale up

    # Sign into 1Password CLI
    eval $(op signin)

    # Run the first-boot setup script
    ~/.local/bin/forge-setup

    # Copy NTFY config
    sudo cp /etc/ardent-forge/ntfy-server.yml.example /data/ntfy/etc/server.yml
    # Edit the base-url to match your tailnet hostname:
    sudo vim /data/ntfy/etc/server.yml

    # Start all services
    sudo systemctl start ardent-forge

## Phase 4: Validate

    # Check all services are running
    systemctl status ardent-forge
    systemctl status postgresql
    systemctl status prometheus
    systemctl status grafana
    systemctl status loki
    systemctl status ollama
    systemctl status podman-ntfy
    systemctl status the-weather
    systemctl status tailscaled
    systemctl status caddy

    # Test Ardent Forge API
    curl http://127.0.0.1:7030/health

    # Test via Tailscale (from Mac)
    curl https://ardent-forge.tail1234.ts.net/health

    # Test Grafana
    curl -s http://127.0.0.1:3000/api/health | jq .

    # Test NTFY
    curl -d "Ardent Forge is alive" http://127.0.0.1:8090/test

    # Test Ollama
    curl http://127.0.0.1:11434/api/tags

    # Check Prometheus targets
    curl http://127.0.0.1:9090/api/v1/targets | jq '.data.activeTargets[].health'

## Phase 5: Commit Hardware Config

After validation, commit the real hardware config back to the repo:

    cd /data/ardent-forge/repo
    git add nix/hardware.nix
    git commit -m "chore(nix): add real Bee Link hardware configuration"
    git push

## Post-Install

- Bookmark Grafana: `https://grafana.ardent-forge.<tailnet>.ts.net`
- Bookmark Ardent Forge: `https://ardent-forge.<tailnet>.ts.net`
- Set up Grafana dashboards for system metrics and Ardent Forge tasks
- Create a Linear issue to test the full pipeline end-to-end
```

- [ ] **Step 2: Commit**

```bash
git add docs/installation.md
git commit -m "docs: add NixOS installation runbook for Bee Link

Step-by-step: USB installer, partitioning, bootstrap, full deploy,
Tailscale setup, 1Password signin, service validation."
```

---

## Summary

| Task | What it creates | Key services |
|------|----------------|--------------|
| 1 | Flake + base config + hardware placeholder | Tailscale, SSH, Podman, firewall |
| 2 | Ardent Forge service | systemd + uv + 1Password |
| 3 | PostgreSQL | PG 17, tuned, prometheus exporter |
| 4 | Monitoring stack | Prometheus, Grafana, Loki, Promtail |
| 5 | Ollama | CPU-only local models |
| 6 | Caddy | HTTPS reverse proxy via Tailscale |
| 7 | NTFY | Podman container for notifications |
| 8 | The Weather | Podman container + 1Password |
| 9 | Home Manager | Dev environment from dotfiles |
| 10 | Installation runbook | Physical install + deploy guide |

Plan complete and saved to `docs/superpowers/plans/2026-04-11-nixos-deployment.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?