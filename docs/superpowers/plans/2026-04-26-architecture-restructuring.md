# Architecture Restructuring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split Ardent Forge into three independent systems (Homelab infrastructure, Ardent Forge for agentic coding, nb for knowledge management), starting from scratch with proven architectural patterns.

**Architecture:** 
- Phase 1: Extract and validate shared infrastructure (NixOS flake, Quadlet, nftables, Ollama)
- Phase 2: Build Ardent Forge from scratch (Rust + Axum + Svelte 5, single binary, modular agents/connectors)
- Phase 3: Build nb from scratch (Python + FastAPI, vault integration, FTS5 indexing, agents)
- Phase 4+: Iteratively develop agents and connectors in both systems

**Tech Stack:** 
- Homelab: NixOS, Quadlet, rootless Podman, agenix, nftables
- Ardent Forge: Rust 1.25.4, Axum, Tokio, SQLite, Svelte 5, SvelteKit, Tailwind CSS 4
- nb: Python 3.13, FastAPI, SQLAlchemy, SQLite (FTS5), Anthropic SDK

---

## Phase 1: Homelab Infrastructure Extraction

### Task 1: Create Homelab repository structure

**Files:**
- Create: `~/Repos/github.com/t-eckert/homelab/flake.nix`
- Create: `~/Repos/github.com/t-eckert/homelab/flake.lock`
- Create: `~/Repos/github.com/t-eckert/homelab/home-manager/default.nix`
- Create: `~/Repos/github.com/t-eckert/homelab/nixos/default.nix`
- Create: `~/Repos/github.com/t-eckert/homelab/README.md`

- [ ] **Step 1: Initialize Homelab repo**

```bash
cd ~/Repos/github.com/t-eckert
mkdir -p homelab
cd homelab
git init
touch README.md
git add README.md
git commit -m "init: create homelab repository"
```

- [ ] **Step 2: Create flake.nix scaffold**

Create `flake.nix`:
```nix
{
  description = "Thomas's Homelab NixOS Configuration";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    home-manager.url = "github:nix-community/home-manager";
    home-manager.inputs.nixpkgs.follows = "nixpkgs";
    flake-utils.url = "github:numtide/flake-utils";
    quadlet-nix.url = "github:SEIAROTg/quadlet-nix";
    quadlet-nix.inputs.nixpkgs.follows = "nixpkgs";
    agenix.url = "github:ryantm/agenix";
    agenix.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, home-manager, flake-utils, quadlet-nix, agenix }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
    in {
      nixosConfigurations.homelab = nixpkgs.lib.nixosSystem {
        inherit system;
        modules = [
          ./nixos/default.nix
          home-manager.nixosModules.home-manager
          {
            home-manager.useGlobalPkgs = true;
            home-manager.useUserPackages = true;
            home-manager.users.thomas = import ./home-manager/default.nix;
          }
          quadlet-nix.nixosModules.quadlet
          agenix.nixosModules.age
        ];
      };
    };
}
```

- [ ] **Step 3: Create nixos/default.nix**

Create `nixos/default.nix`:
```nix
{ config, pkgs, ... }:

{
  system.stateVersion = "24.11";

  # Networking
  networking.hostName = "homelab";
  networking.networkmanager.enable = true;

  # Virtualization and containers
  virtualisation.podman.enable = true;
  virtualisation.podman.dockerCompat = true;
  virtualisation.quadlet.enable = true;

  # Users
  users.users.thomas = {
    isNormalUser = true;
    extraGroups = [ "wheel" "podman" ];
    linger = true;
  };

  users.users.thomas.autoSubUidGidRange = true;

  # SSH
  services.openssh.enable = true;
  services.openssh.settings.PermitRootLogin = "no";

  # Tailscale
  services.tailscale.enable = true;

  # NTP
  services.timesyncd.enable = true;

  # Firewall
  networking.firewall.enable = true;
  networking.firewall.allowedTCPPorts = [ 22 ];

  # Locale
  time.timeZone = "America/Toronto";
  i18n.defaultLocale = "en_US.UTF-8";
}
```

- [ ] **Step 4: Create home-manager/default.nix**

Create `home-manager/default.nix`:
```nix
{ config, pkgs, ... }:

{
  home.stateVersion = "24.11";
  home.homeDirectory = "/home/thomas";
  home.username = "thomas";

  # User packages
  home.packages = with pkgs; [
    git
    curl
    ripgrep
    fd
    jq
    vim
    htop
  ];

  # Git configuration
  programs.git = {
    enable = true;
    userName = "Thomas Eckert";
    userEmail = "thomas.james.eckert@gmail.com";
  };

  # Bash
  programs.bash.enable = true;
}
```

- [ ] **Step 5: Create README.md**

```markdown
# Homelab

NixOS configuration for personal homelab running Ardent Forge, nb, and supporting services.

## Structure

- `flake.nix` — Flake inputs and outputs
- `nixos/default.nix` — NixOS system configuration
- `home-manager/default.nix` — User home configuration
- `services/` — Quadlet service definitions (to be created)
- `secrets/` — agenix encrypted secrets (not in git)

## Quick Start

```bash
sudo nixos-rebuild switch --flake .
```
```

- [ ] **Step 6: Commit**

```bash
git add flake.nix nixos/default.nix home-manager/default.nix README.md
git commit -m "feat: scaffold homelab NixOS flake with quadlet and agenix"
```

---

### Task 2: Set up rootless Podman with Quadlet

**Files:**
- Create: `home-manager/podman.nix`
- Modify: `home-manager/default.nix`

- [ ] **Step 1: Create podman.nix configuration**

Create `home-manager/podman.nix`:
```nix
{ config, pkgs, ... }:

{
  # User-level Quadlet units directory
  systemd.user.targets.podman-compose = {
    Unit = {
      Description = "Podman Compose Target";
      After = "default.target";
    };
    Install.WantedBy = [ "default.target" ];
  };

  # Enable user lingering (needed for user services to survive logout)
  # This is set at the system level in nixos/default.nix with linger = true

  # Enable Podman socket activation for rootless operation
  systemd.user.services.podman = {
    Unit = {
      Description = "Podman API Service";
      Documentation = "man:podman-system-service(1)";
      Requires = "podman.socket";
      After = "podman.socket";
      StartLimitIntervalSec = 0;
    };
    Service = {
      Type = "exec";
      KillMode = "process";
      Environment = "LOGGING=file";
      ExecStart = "${pkgs.podman}/bin/podman system service";
      StandardOutput = "journal";
      StandardError = "journal";
      Restart = "on-failure";
      RestartSec = "5";
    };
  };

  systemd.user.sockets.podman = {
    Unit = {
      Description = "Podman API Socket";
      Documentation = "man:podman-system-service(1)";
    };
    Socket = {
      ListenStream = "%t/podman/podman.sock";
      SocketMode = "0600";
    };
    Install.WantedBy = [ "sockets.target" ];
  };
}
```

- [ ] **Step 2: Include podman.nix in home-manager/default.nix**

Update `home-manager/default.nix` to include:
```nix
{ config, pkgs, ... }:

{
  imports = [ ./podman.nix ];

  # ... rest of configuration
}
```

- [ ] **Step 3: Verify nftables is available for later use**

Update `nixos/default.nix` to include:
```nix
  # nftables for network filtering
  networking.nftables.enable = true;
  networking.nftables.ruleset = ''
    # Placeholder for container egress rules (to be populated later)
    table inet filter {
      chain forward {
        type filter hook forward priority filter; policy drop;
        ct state established,related accept
      }
    }
  '';
```

- [ ] **Step 4: Commit**

```bash
git add home-manager/podman.nix home-manager/default.nix nixos/default.nix
git commit -m "feat: configure rootless podman with systemd user socket activation"
```

---

### Task 3: Set up Ollama container for embeddings

**Files:**
- Create: `services/ollama.container`
- Create: `services/ollama.volume`

- [ ] **Step 1: Create Ollama Quadlet unit**

Create `services/ollama.container`:
```ini
[Unit]
Description=Ollama Embedding Service
After=podman-network-default.network
Wants=network-online.target
StartLimitIntervalSec=0

[Container]
Image=ollama/ollama:latest
ContainerName=ollama
Network=default
Exec=serve
Environment=OLLAMA_HOST=unix:///run/podman/ollama.sock
Volume=%h/.local/share/ollama:/root/.ollama:z
Socket=%t/podman/ollama.sock:0600:065534:uid

[Service]
Type=notify
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target default.target
```

- [ ] **Step 2: Create volume for Ollama state**

Create `services/ollama.volume`:
```ini
[Unit]
Description=Ollama Data Volume
PartOf=ollama.service

[Volume]
VolumeName=ollama-data

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 3: Document Ollama model pull**

Create `docs/ollama-setup.md`:
```markdown
# Ollama Setup

The Ollama container will start automatically via Quadlet.

## Pulling the embedding model

Once the container is running, pull the embedding model:

```bash
podman exec ollama ollama pull nomic-embed-text-v2-moe
```

This downloads ~2GB and provides the `nomic-embed-text-v2-moe` model for vector embeddings used by `nb`.

## Verifying the model

```bash
podman exec ollama ollama list
```

Should show `nomic-embed-text-v2-moe:latest` installed.
```

- [ ] **Step 4: Commit**

```bash
git add services/ollama.container services/ollama.volume docs/ollama-setup.md
git commit -m "feat: add ollama quadlet unit for embeddings service"
```

---

### Task 4: Configure network egress rules with nftables

**Files:**
- Create: `nixos/nftables.nix`
- Modify: `nixos/default.nix`

- [ ] **Step 1: Create nftables configuration module**

Create `nixos/nftables.nix`:
```nix
{ config, ... }:

{
  networking.nftables.enable = true;
  networking.nftables.ruleset = ''
    table inet filter {
      chain input {
        type filter hook input priority filter; policy accept;
        iif lo accept
        ct state established,related accept
        tcp dport 22 accept
        tcp dport 80 accept
        tcp dport 443 accept
      }

      chain forward {
        type filter hook forward priority filter; policy drop;
        ct state established,related accept

        # Allow outbound from containers to specific domains
        # Format: allow traffic to <domain> on port 443 from ardent-forge and nb containers

        # Anthropic API
        oifname "br-*" tcp dport 443 ct mark set 1 counter
        ct mark 1 counter

        # Telegram Bot API
        oifname "br-*" tcp dport 443 ct mark set 2 counter
        ct mark 2 counter

        # GitHub (for vault pushes)
        oifname "br-*" tcp dport 443 ct mark set 3 counter
        ct mark 3 counter

        # Strava API
        oifname "br-*" tcp dport 443 ct mark set 4 counter
        ct mark 4 counter

        # Linear API (internal, via Tailscale)
        oifname "tailscale0" tcp dport 443 accept

        # DNS (to system resolver)
        oifname "br-*" udp dport 53 accept
      }

      chain output {
        type filter hook output priority filter; policy accept;
      }
    }
  '';
}
```

- [ ] **Step 2: Include nftables module in nixos/default.nix**

Update `nixos/default.nix`:
```nix
{ config, pkgs, ... }:

{
  imports = [ ./nftables.nix ];

  # ... rest of configuration
}
```

- [ ] **Step 3: Document egress policy**

Create `docs/network-security.md`:
```markdown
# Network Egress Security

Containers run with a default-deny egress policy enforced by nftables on the host.

## Allowed destinations (per container, TBD):

### Ardent Forge
- api.anthropic.com (Anthropic API)
- github.com (GitHub for source control)
- api.linear.app (Linear API, via Tailscale)

### nb
- api.anthropic.com (Anthropic API for Claude calls)
- api.telegram.org (Telegram Bot API)
- api.github.com (GitHub for vault pushes)
- api.strava.com (Strava API for activity webhooks)

### DNS
- 127.0.0.1:53 (system resolver)

## Tailscale routes
- 100.0.0.0/8 (Tailscale subnet for internal services)

## Adding new destinations

1. Audit the container to determine required domains
2. Add nftables rule in `nixos/nftables.nix`
3. Rebuild with `sudo nixos-rebuild switch`
```

- [ ] **Step 4: Commit**

```bash
git add nixos/nftables.nix nixos/default.nix docs/network-security.md
git commit -m "feat: configure nftables egress filtering for container security"
```

---

### Task 5: Set up agenix for secrets management

**Files:**
- Create: `secrets/secrets.nix`
- Create: `secrets/.gitignore`
- Create: `docs/secrets-setup.md`
- Modify: `nixos/default.nix`

- [ ] **Step 1: Create secrets configuration**

Create `secrets/secrets.nix`:
```nix
let
  thomasKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI..."; # Your SSH public key
in
{
  "anthropic-api-key.age".publicKeys = [ thomasKey ];
  "linear-api-key.age".publicKeys = [ thomasKey ];
  "telegram-bot-token.age".publicKeys = [ thomasKey ];
  "strava-webhook-secret.age".publicKeys = [ thomasKey ];
  "github-pat.age".publicKeys = [ thomasKey ];
}
```

- [ ] **Step 2: Create .gitignore for secrets**

Create `secrets/.gitignore`:
```
*.age
!secrets.nix
```

- [ ] **Step 3: Create secrets documentation**

Create `docs/secrets-setup.md`:
```markdown
# Secrets Management with agenix

Secrets are encrypted with your SSH key and stored in `secrets/`.

## Initial setup

1. Get your SSH public key:
```bash
cat ~/.ssh/id_ed25519.pub
```

2. Update `secrets/secrets.nix` with your public key

3. Create secrets (you'll be prompted to edit them):
```bash
agenix -e anthropic-api-key.age
agenix -e linear-api-key.age
agenix -e telegram-bot-token.age
agenix -e strava-webhook-secret.age
agenix -e github-pat.age
```

## Usage in NixOS

Secrets are automatically decrypted and available to services at runtime.

In Quadlet container units, inject as environment variables:
```ini
Environment=ANTHROPIC_API_KEY=%d/run/agenix/anthropic-api-key
```

The file is mounted read-only at `/run/agenix/`.
```

- [ ] **Step 4: Update nixos/default.nix to import agenix**

Update `nixos/default.nix`:
```nix
{ config, pkgs, ... }:

{
  imports = [ ./nftables.nix ];

  age.secrets.anthropic-api-key.file = ../secrets/anthropic-api-key.age;
  age.secrets.linear-api-key.file = ../secrets/linear-api-key.age;
  age.secrets.telegram-bot-token.file = ../secrets/telegram-bot-token.age;
  age.secrets.strava-webhook-secret.file = ../secrets/strava-webhook-secret.age;
  age.secrets.github-pat.file = ../secrets/github-pat.age;

  # ... rest of configuration
}
```

- [ ] **Step 5: Commit**

```bash
git add secrets/secrets.nix secrets/.gitignore docs/secrets-setup.md nixos/default.nix
git commit -m "feat: add agenix secrets management for API keys and credentials"
```

---

### Task 6: Verify Homelab infrastructure locally (dry-run)

**Files:**
- None (verification only)

- [ ] **Step 1: Check flake.nix syntax**

```bash
cd ~/Repos/github.com/t-eckert/homelab
nix flake check
```

Expected output: No errors

- [ ] **Step 2: Evaluate NixOS config**

```bash
nix eval --file '<nixpkgs/lib>' 'import ./nixos/default.nix'
```

Expected output: No errors

- [ ] **Step 3: List all Quadlet units**

```bash
ls -la services/
```

Expected output:
```
ollama.container
ollama.volume
```

- [ ] **Step 4: Document remaining infrastructure tasks**

Create `docs/homelab-roadmap.md`:
```markdown
# Homelab Infrastructure Roadmap

## Phase 1: Complete ✓
- [x] NixOS flake scaffold
- [x] Quadlet rootless Podman setup
- [x] Ollama container for embeddings
- [x] nftables egress filtering
- [x] agenix secrets management

## Phase 2: Ardent Forge Infrastructure (TBD)
- [ ] Quadlet unit for ardent-forge container
- [ ] Shared network configuration
- [ ] Health check endpoints
- [ ] Monitoring integration (Grafana, Prometheus)

## Phase 3: nb Infrastructure (TBD)
- [ ] Quadlet unit for nb container
- [ ] Vault mount configuration
- [ ] Health check endpoints
- [ ] Monitoring integration

## Phase 4+: Advanced (TBD)
- [ ] Log aggregation (Loki)
- [ ] Distributed tracing (Tempo)
- [ ] Backup automation
```

- [ ] **Step 5: Final commit**

```bash
git add docs/homelab-roadmap.md
git commit -m "docs: document homelab infrastructure completion and roadmap"
```

---

## Phase 2: Ardent Forge from Scratch (Rust + Axum + Svelte 5)

### Task 7: Initialize Ardent Forge Rust project

**Files:**
- Create: `Cargo.toml`
- Create: `src/main.rs`
- Create: `src/lib.rs`
- Create: `Cargo.lock`
- Create: `.gitignore`

- [ ] **Step 1: Create new Rust project**

```bash
cd ~/Repos/github.com/t-eckert/ardent-forge
rm -rf src/ Cargo.toml  # Remove old python-based files if starting fresh
cargo init --name ardent_forge
```

- [ ] **Step 2: Update Cargo.toml with dependencies**

Update `Cargo.toml`:
```toml
[package]
name = "ardent_forge"
version = "0.1.0"
edition = "2021"

[dependencies]
axum = "0.7"
tokio = { version = "1", features = ["full"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
sqlx = { version = "0.7", features = ["runtime-tokio-rustls", "sqlite"] }
rusqlite = { version = "0.30", features = ["bundled"] }
uuid = { version = "1.0", features = ["v4", "serde"] }
chrono = { version = "0.4", features = ["serde"] }
anyhow = "1.0"
thiserror = "1.0"
tracing = "0.1"
tracing-subscriber = "0.3"
tower = "0.4"
tower-http = { version = "0.5", features = ["trace", "cors"] }
futures = "0.3"
clap = { version = "4.4", features = ["derive"] }
dotenv = "0.15"

[dev-dependencies]
tokio-test = "0.4"
```

- [ ] **Step 3: Create src/lib.rs**

Create `src/lib.rs`:
```rust
pub mod agents;
pub mod connectors;
pub mod coordinator;
pub mod models;
pub mod store;

pub use coordinator::Coordinator;
```

- [ ] **Step 4: Create src/main.rs scaffold**

Create `src/main.rs`:
```rust
use axum::{
    routing::get,
    Router,
};
use std::net::SocketAddr;
use tracing::info;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();

    let app = Router::new()
        .route("/health", get(health_check));

    let addr = SocketAddr::from(([127, 0, 0, 1], 7030));
    info!("Ardent Forge listening on {}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}

async fn health_check() -> &'static str {
    "ok"
}
```

- [ ] **Step 5: Create module placeholders**

```bash
mkdir -p src/agents src/connectors
touch src/agents.rs src/connectors.rs src/coordinator.rs src/models.rs src/store.rs
```

Update each placeholder (e.g., `src/agents.rs`):
```rust
//! Agent implementations
```

- [ ] **Step 6: Verify build**

```bash
cargo build 2>&1 | head -20
```

Expected: No errors (may have warnings about unused code)

- [ ] **Step 7: Commit**

```bash
git add Cargo.toml Cargo.lock src/main.rs src/lib.rs src/agents.rs src/connectors.rs src/coordinator.rs src/models.rs src/store.rs .gitignore
git commit -m "feat: initialize rust project with axum and core dependencies"
```

---

### Task 8: Set up SQLite schema for Ardent Forge

**Files:**
- Create: `migrations/001_init.sql`
- Create: `src/db.rs`
- Modify: `src/lib.rs`
- Modify: `Cargo.toml`

- [ ] **Step 1: Create migrations directory**

```bash
mkdir -p migrations
```

- [ ] **Step 2: Create initial schema**

Create `migrations/001_init.sql`:
```sql
-- Tasks table
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'queued',
    priority INTEGER DEFAULT 3,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    started_at DATETIME,
    completed_at DATETIME,
    agent_type TEXT,
    linear_issue_id TEXT UNIQUE
);

-- Thread messages table
CREATE TABLE IF NOT EXISTS thread_messages (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    message_type TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    user_id TEXT,
    task_id TEXT REFERENCES tasks(id)
);

-- Sessions table (Claude Code invocations)
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    project_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'starting',
    prompt TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    started_at DATETIME,
    completed_at DATETIME,
    container_id TEXT,
    process_id INTEGER,
    claude_session_id TEXT UNIQUE
);

-- Session events (streaming output)
CREATE TABLE IF NOT EXISTS session_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    event_type TEXT NOT NULL,
    event_data TEXT NOT NULL,
    created_at DATETIME NOT NULL
);

-- Cost tracking
CREATE TABLE IF NOT EXISTS cost_records (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES sessions(id),
    model_id TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    recorded_at DATETIME NOT NULL
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_thread_messages_thread_id ON thread_messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_sessions_task_id ON sessions(task_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_session_events_session_id ON session_events(session_id);
CREATE INDEX IF NOT EXISTS idx_cost_records_session_id ON cost_records(session_id);
```

- [ ] **Step 3: Create db.rs module**

Create `src/db.rs`:
```rust
use rusqlite::{Connection, Result as SqliteResult};
use std::path::Path;

pub struct Database {
    conn: Connection,
}

impl Database {
    pub fn new(path: impl AsRef<Path>) -> SqliteResult<Self> {
        let conn = Connection::open(path)?;
        conn.execute_batch("PRAGMA journal_mode = WAL;")?;
        Ok(Database { conn })
    }

    pub fn initialize(&self) -> SqliteResult<()> {
        let sql = include_str!("../migrations/001_init.sql");
        self.conn.execute_batch(sql)?;
        Ok(())
    }

    pub fn connection(&self) -> &Connection {
        &self.conn
    }
}
```

- [ ] **Step 4: Update lib.rs to include db module**

Update `src/lib.rs`:
```rust
pub mod agents;
pub mod connectors;
pub mod coordinator;
pub mod db;
pub mod models;
pub mod store;

pub use coordinator::Coordinator;
pub use db::Database;
```

- [ ] **Step 5: Update main.rs to initialize database**

Update `src/main.rs`:
```rust
use ardent_forge::Database;
use axum::{
    routing::get,
    Router,
};
use std::net::SocketAddr;
use tracing::info;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();

    // Initialize database
    let db = Database::new("/tmp/ardent_forge.db")?;
    db.initialize()?;
    info!("Database initialized");

    let app = Router::new()
        .route("/health", get(health_check));

    let addr = SocketAddr::from(([127, 0, 0, 1], 7030));
    info!("Ardent Forge listening on {}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}

async fn health_check() -> &'static str {
    "ok"
}
```

- [ ] **Step 6: Test database initialization**

```bash
cargo build --release 2>&1 | grep -i error
```

Expected: No errors

- [ ] **Step 7: Commit**

```bash
git add migrations/001_init.sql src/db.rs src/lib.rs src/main.rs
git commit -m "feat: add sqlite schema and database initialization"
```

---

### Task 9: Create modular agent framework

**Files:**
- Create: `src/agents/agent.rs`
- Create: `src/agents/mod.rs`
- Create: `src/agents/code.rs`
- Create: `src/agents/plan.rs`

- [ ] **Step 1: Define Agent trait**

Create `src/agents/agent.rs`:
```rust
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Stage {
    Triage,
    Execute,
    Verify,
    Deliver,
}

#[async_trait::async_trait]
pub trait Agent: Send + Sync {
    /// Returns the name of this agent
    fn name(&self) -> &'static str;

    /// Returns which stages this agent implements
    fn stages(&self) -> Vec<Stage>;

    /// Triage stage: return true to proceed
    async fn triage(&self, task: &Task) -> anyhow::Result<bool> {
        Ok(true)
    }

    /// Execute stage: perform the work
    async fn execute(&self, task: &Task) -> anyhow::Result<TaskResult> {
        Err(anyhow::anyhow!("execute not implemented"))
    }

    /// Verify stage: check the work
    async fn verify(&self, task: &Task, result: &TaskResult) -> anyhow::Result<bool> {
        Ok(true)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Task {
    pub id: String,
    pub title: String,
    pub description: Option<String>,
    pub status: TaskStatus,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum TaskStatus {
    Queued,
    Triaging,
    Executing,
    Verifying,
    Delivering,
    Completed,
    Failed,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskResult {
    pub task_id: String,
    pub output: String,
}
```

- [ ] **Step 2: Update Cargo.toml with async_trait**

Update `Cargo.toml` dependencies section:
```toml
async-trait = "0.1"
```

- [ ] **Step 3: Create agents/mod.rs**

Create `src/agents/mod.rs`:
```rust
pub mod agent;
pub mod code;
pub mod plan;

pub use agent::{Agent, Stage, Task, TaskResult, TaskStatus};
pub use code::CodeAgent;
pub use plan::PlanAgent;
```

- [ ] **Step 4: Implement CodeAgent**

Create `src/agents/code.rs`:
```rust
use async_trait::async_trait;
use crate::agents::{Agent, Stage, Task, TaskResult};

pub struct CodeAgent;

#[async_trait]
impl Agent for CodeAgent {
    fn name(&self) -> &'static str {
        "code"
    }

    fn stages(&self) -> Vec<Stage> {
        vec![Stage::Triage, Stage::Execute, Stage::Verify]
    }

    async fn execute(&self, task: &Task) -> anyhow::Result<TaskResult> {
        // Placeholder: actual implementation will spawn Claude Code session
        Ok(TaskResult {
            task_id: task.id.clone(),
            output: format!("Executed task: {}", task.title),
        })
    }
}
```

- [ ] **Step 5: Implement PlanAgent**

Create `src/agents/plan.rs`:
```rust
use async_trait::async_trait;
use crate::agents::{Agent, Stage, Task, TaskResult};

pub struct PlanAgent;

#[async_trait]
impl Agent for PlanAgent {
    fn name(&self) -> &'static str {
        "plan"
    }

    fn stages(&self) -> Vec<Stage> {
        vec![Stage::Verify]
    }

    async fn verify(&self, task: &Task, result: &TaskResult) -> anyhow::Result<bool> {
        // Placeholder: actual implementation will verify plan was executed correctly
        tracing::info!("Plan agent verifying task: {}", task.id);
        Ok(true)
    }
}
```

- [ ] **Step 6: Update lib.rs**

Update `src/lib.rs`:
```rust
pub mod agents;
pub mod connectors;
pub mod coordinator;
pub mod db;
pub mod models;
pub mod store;

pub use agents::{Agent, CodeAgent, PlanAgent};
pub use coordinator::Coordinator;
pub use db::Database;
```

- [ ] **Step 7: Verify compilation**

```bash
cargo check 2>&1 | grep -i error
```

Expected: No errors

- [ ] **Step 8: Commit**

```bash
git add src/agents/agent.rs src/agents/code.rs src/agents/plan.rs src/agents/mod.rs src/lib.rs Cargo.toml
git commit -m "feat: implement modular agent framework with stage gates"
```

---

### Task 10: Create coordinator for stage sequencing

**Files:**
- Create: `src/coordinator.rs`
- Modify: `src/lib.rs`

- [ ] **Step 1: Implement Coordinator**

Create `src/coordinator.rs`:
```rust
use crate::agents::{Agent, Stage, Task, TaskResult};
use std::sync::Arc;

pub struct Coordinator {
    agents: Vec<Arc<dyn Agent>>,
}

impl Coordinator {
    pub fn new(agents: Vec<Arc<dyn Agent>>) -> Self {
        Coordinator { agents }
    }

    pub async fn execute_task(&self, mut task: Task) -> anyhow::Result<TaskResult> {
        let stages = vec![Stage::Triage, Stage::Execute, Stage::Verify];

        for stage in stages {
            let agents_for_stage: Vec<_> = self
                .agents
                .iter()
                .filter(|a| a.stages().contains(&stage))
                .collect();

            for agent in agents_for_stage {
                match stage {
                    Stage::Triage => {
                        if !agent.triage(&task).await? {
                            return Err(anyhow::anyhow!("Triage failed for agent: {}", agent.name()));
                        }
                    }
                    Stage::Execute => {
                        let result = agent.execute(&task).await?;
                        return Ok(result);
                    }
                    Stage::Verify => {
                        let result = TaskResult {
                            task_id: task.id.clone(),
                            output: "verified".to_string(),
                        };
                        if !agent.verify(&task, &result).await? {
                            return Err(anyhow::anyhow!("Verification failed"));
                        }
                    }
                    _ => {}
                }
            }
        }

        Err(anyhow::anyhow!("No agent could execute this task"))
    }
}
```

- [ ] **Step 2: Update lib.rs**

Update `src/lib.rs`:
```rust
pub mod agents;
pub mod connectors;
pub mod coordinator;
pub mod db;
pub mod models;
pub mod store;

pub use agents::{Agent, CodeAgent, PlanAgent, Stage, Task, TaskResult, TaskStatus};
pub use coordinator::Coordinator;
pub use db::Database;
```

- [ ] **Step 3: Add coordinator test**

Create `tests/coordinator_test.rs`:
```rust
use ardent_forge::{Coordinator, CodeAgent, Task, TaskStatus};
use std::sync::Arc;

#[tokio::test]
async fn test_coordinator_executes_task() {
    let agents: Vec<Arc<dyn _>> = vec![
        Arc::new(CodeAgent),
    ];
    let coordinator = Coordinator::new(agents);

    let task = Task {
        id: "test-1".to_string(),
        title: "Test task".to_string(),
        description: None,
        status: TaskStatus::Queued,
    };

    let result = coordinator.execute_task(task).await;
    assert!(result.is_ok());
    assert_eq!(result.unwrap().output, "Executed task: Test task");
}
```

- [ ] **Step 4: Run tests**

```bash
cargo test --test coordinator_test 2>&1
```

Expected: `test coordinator_test::test_coordinator_executes_task ... ok`

- [ ] **Step 5: Commit**

```bash
git add src/coordinator.rs tests/coordinator_test.rs src/lib.rs
git commit -m "feat: implement coordinator for task stage sequencing"
```

---

### Task 11: Add Linear integration (poller)

**Files:**
- Create: `src/connectors/linear.rs`
- Create: `src/connectors/mod.rs`
- Modify: `Cargo.toml`
- Modify: `src/lib.rs`

- [ ] **Step 1: Add http client dependency**

Update `Cargo.toml`:
```toml
reqwest = { version = "0.11", features = ["json"] }
```

- [ ] **Step 2: Create Linear connector**

Create `src/connectors/linear.rs`:
```rust
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LinearIssue {
    pub id: String,
    pub identifier: String,
    pub title: String,
    pub description: Option<String>,
}

pub struct LinearClient {
    api_key: String,
    base_url: String,
}

impl LinearClient {
    pub fn new(api_key: String) -> Self {
        LinearClient {
            api_key,
            base_url: "https://api.linear.app/graphql".to_string(),
        }
    }

    pub async fn fetch_issues(&self) -> anyhow::Result<Vec<LinearIssue>> {
        // Placeholder: actual implementation will query Linear API
        // For now, return empty list
        Ok(vec![])
    }

    pub async fn create_issue_comment(&self, issue_id: &str, comment: &str) -> anyhow::Result<()> {
        // Placeholder: actual implementation will post comment
        tracing::info!("Posting comment to issue {}: {}", issue_id, comment);
        Ok(())
    }
}
```

- [ ] **Step 3: Create connectors/mod.rs**

Create `src/connectors/mod.rs`:
```rust
pub mod linear;

pub use linear::{LinearClient, LinearIssue};
```

- [ ] **Step 4: Update lib.rs**

Update `src/lib.rs`:
```rust
pub mod agents;
pub mod connectors;
pub mod coordinator;
pub mod db;
pub mod models;
pub mod store;

pub use agents::{Agent, CodeAgent, PlanAgent, Stage, Task, TaskResult, TaskStatus};
pub use connectors::LinearClient;
pub use coordinator::Coordinator;
pub use db::Database;
```

- [ ] **Step 5: Create Linear poller**

Create `src/poller.rs`:
```rust
use crate::connectors::LinearClient;
use tracing::info;

pub struct LinearPoller {
    client: LinearClient,
}

impl LinearPoller {
    pub fn new(client: LinearClient) -> Self {
        LinearPoller { client }
    }

    pub async fn poll(&self) -> anyhow::Result<()> {
        info!("Polling Linear for new issues");
        let _issues = self.client.fetch_issues().await?;
        // TODO: Convert issues to tasks and enqueue
        Ok(())
    }
}
```

- [ ] **Step 6: Update lib.rs to include poller**

Update `src/lib.rs`:
```rust
pub mod agents;
pub mod connectors;
pub mod coordinator;
pub mod db;
pub mod models;
pub mod poller;
pub mod store;

pub use agents::{Agent, CodeAgent, PlanAgent, Stage, Task, TaskResult, TaskStatus};
pub use connectors::LinearClient;
pub use coordinator::Coordinator;
pub use db::Database;
pub use poller::LinearPoller;
```

- [ ] **Step 7: Verify compilation**

```bash
cargo check 2>&1 | grep -i error
```

Expected: No errors

- [ ] **Step 8: Commit**

```bash
git add src/connectors/linear.rs src/connectors/mod.rs src/poller.rs src/lib.rs Cargo.toml
git commit -m "feat: add Linear client and poller for task ingestion"
```

---

### Task 12: Set up Svelte 5 frontend in same repo

**Files:**
- Create: `ui/package.json`
- Create: `ui/svelte.config.js`
- Create: `ui/vite.config.ts`
- Create: `ui/tsconfig.json`
- Create: `ui/src/app.svelte`
- Create: `build.rs` (Rust build script)

- [ ] **Step 1: Initialize UI directory**

```bash
mkdir -p ui/src
```

- [ ] **Step 2: Create package.json**

Create `ui/package.json`:
```json
{
  "name": "ardent-forge-ui",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "devDependencies": {
    "@sveltejs/vite-plugin-svelte": "^3.0.0",
    "svelte": "^5.0.0",
    "typescript": "^5.0.0",
    "vite": "^5.0.0",
    "tailwindcss": "^4.0.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0"
  }
}
```

- [ ] **Step 3: Create vite.config.ts**

Create `ui/vite.config.ts`:
```typescript
import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: '../dist',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:7030',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 4: Create svelte.config.js**

Create `ui/svelte.config.js`:
```javascript
import adapter from '@sveltejs/adapter-static'

export default {
  kit: {
    adapter: adapter({
      fallback: 'index.html',
    }),
  },
}
```

- [ ] **Step 5: Create tsconfig.json**

Create `ui/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "baseUrl": ".",
    "paths": {
      "$lib/*": ["./src/lib/*"]
    }
  },
  "include": ["src/**/*.ts", "src/**/*.svelte"],
  "exclude": ["node_modules", "dist"]
}
```

- [ ] **Step 6: Create minimal Svelte component**

Create `ui/src/app.svelte`:
```svelte
<script lang="ts">
  import '../app.css'
  let count = $state(0)
</script>

<main class="flex flex-col items-center justify-center min-h-screen">
  <h1 class="text-4xl font-bold">Ardent Forge</h1>
  <p class="text-lg text-gray-600 mt-2">Agentic coding control plane</p>
  <button
    onclick={() => count++}
    class="mt-8 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
  >
    Count: {count}
  </button>
</main>

<style>
  :global(body) {
    margin: 0;
    padding: 0;
  }
</style>
```

- [ ] **Step 7: Create app.css**

Create `ui/src/app.css`:
```css
@import "tailwindcss";
```

- [ ] **Step 8: Create Rust build script to build frontend**

Create `build.rs`:
```rust
use std::process::Command;

fn main() {
    // Build Svelte UI
    let output = Command::new("npm")
        .args(&["--prefix", "ui", "run", "build"])
        .output();

    match output {
        Ok(output) => {
            if !output.status.success() {
                panic!("Frontend build failed: {:?}", String::from_utf8_lossy(&output.stderr));
            }
        }
        Err(e) => {
            eprintln!("Warning: Could not build frontend: {}", e);
            eprintln!("Ensure npm is installed and ui/package.json exists");
        }
    }

    println!("cargo:rerun-if-changed=ui/src");
    println!("cargo:rerun-if-changed=ui/package.json");
}
```

- [ ] **Step 9: Update main.rs to serve static files**

Update `src/main.rs`:
```rust
use axum::{
    routing::get,
    Router,
    http::StatusCode,
};
use std::net::SocketAddr;
use std::path::PathBuf;
use tower_http::services::ServeDir;
use tracing::info;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();

    let app = Router::new()
        .route("/api/health", get(health_check))
        .nest_service("/", ServeDir::new("dist"));

    let addr = SocketAddr::from(([127, 0, 0, 1], 7030));
    info!("Ardent Forge listening on http://{}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}

async fn health_check() -> &'static str {
    "ok"
}
```

- [ ] **Step 10: Commit**

```bash
git add ui/package.json ui/svelte.config.js ui/vite.config.ts ui/tsconfig.json ui/src/app.svelte ui/src/app.css build.rs src/main.rs
git commit -m "feat: add svelte 5 frontend built into rust binary"
```

---

### Task 13: Add Chat/Threads API endpoints

**Files:**
- Create: `src/models/thread.rs`
- Create: `src/api/threads.rs`
- Create: `src/api/mod.rs`
- Modify: `src/main.rs`

- [ ] **Step 1: Create thread models**

Create `src/models/thread.rs`:
```rust
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Thread {
    pub id: String,
    pub title: String,
    pub created_at: String,
    pub messages: Vec<ThreadMessage>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThreadMessage {
    pub id: String,
    pub thread_id: String,
    pub message_type: String, // "text", "task_dispatched", "task_resolved"
    pub content: String,
    pub created_at: String,
    pub task_id: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CreateMessageRequest {
    pub thread_id: String,
    pub content: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct DispatchTaskRequest {
    pub thread_id: String,
    pub title: String,
    pub description: Option<String>,
}
```

- [ ] **Step 2: Create models/mod.rs**

Create `src/models/mod.rs`:
```rust
pub mod thread;

pub use thread::{Thread, ThreadMessage, CreateMessageRequest, DispatchTaskRequest};
```

- [ ] **Step 3: Update lib.rs to include models**

Update `src/lib.rs`:
```rust
pub mod agents;
pub mod connectors;
pub mod coordinator;
pub mod db;
pub mod models;
pub mod poller;
pub mod store;

pub use agents::{Agent, CodeAgent, PlanAgent, Stage, Task, TaskResult, TaskStatus};
pub use connectors::LinearClient;
pub use coordinator::Coordinator;
pub use db::Database;
pub use models::{Thread, ThreadMessage, CreateMessageRequest, DispatchTaskRequest};
pub use poller::LinearPoller;
```

- [ ] **Step 4: Create threads API**

Create `src/api/threads.rs`:
```rust
use axum::{
    extract::{Path, Json},
    response::IntoResponse,
    http::StatusCode,
};
use serde_json::json;
use crate::models::{CreateMessageRequest, DispatchTaskRequest, ThreadMessage};

pub async fn get_threads() -> impl IntoResponse {
    Json(json!({
        "threads": []
    }))
}

pub async fn get_thread(Path(id): Path<String>) -> impl IntoResponse {
    Json(json!({
        "id": id,
        "title": "Example Thread",
        "messages": [],
        "created_at": "2026-04-26T00:00:00Z"
    }))
}

pub async fn post_message(
    Path(id): Path<String>,
    Json(req): Json<CreateMessageRequest>,
) -> impl IntoResponse {
    let message = ThreadMessage {
        id: uuid::Uuid::new_v4().to_string(),
        thread_id: id,
        message_type: "text".to_string(),
        content: req.content,
        created_at: chrono::Utc::now().to_rfc3339(),
        task_id: None,
    };

    (StatusCode::CREATED, Json(message))
}

pub async fn dispatch_task(
    Path(id): Path<String>,
    Json(req): Json<DispatchTaskRequest>,
) -> impl IntoResponse {
    let task = ThreadMessage {
        id: uuid::Uuid::new_v4().to_string(),
        thread_id: id,
        message_type: "task_dispatched".to_string(),
        content: req.title,
        created_at: chrono::Utc::now().to_rfc3339(),
        task_id: Some(uuid::Uuid::new_v4().to_string()),
    };

    (StatusCode::CREATED, Json(task))
}
```

- [ ] **Step 5: Create api/mod.rs**

Create `src/api/mod.rs`:
```rust
pub mod threads;
```

- [ ] **Step 6: Update main.rs with API routes**

Update `src/main.rs`:
```rust
use axum::{
    routing::{get, post},
    Router,
};
use std::net::SocketAddr;
use tower_http::services::ServeDir;
use tracing::info;

mod api;
use api::threads;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();

    let app = Router::new()
        .route("/api/health", get(health_check))
        .route("/api/threads", get(threads::get_threads))
        .route("/api/threads/:id", get(threads::get_thread))
        .route("/api/threads/:id/messages", post(threads::post_message))
        .route("/api/threads/:id/dispatch", post(threads::dispatch_task))
        .nest_service("/", ServeDir::new("dist"));

    let addr = SocketAddr::from(([127, 0, 0, 1], 7030));
    info!("Ardent Forge listening on http://{}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}

async fn health_check() -> &'static str {
    "ok"
}
```

- [ ] **Step 7: Add api module to lib.rs**

Update `src/lib.rs`:
```rust
pub mod agents;
pub mod api;
pub mod connectors;
pub mod coordinator;
pub mod db;
pub mod models;
pub mod poller;
pub mod store;

pub use agents::{Agent, CodeAgent, PlanAgent, Stage, Task, TaskResult, TaskStatus};
pub use connectors::LinearClient;
pub use coordinator::Coordinator;
pub use db::Database;
pub use models::{Thread, ThreadMessage, CreateMessageRequest, DispatchTaskRequest};
pub use poller::LinearPoller;
```

- [ ] **Step 8: Verify build**

```bash
cargo check 2>&1 | grep -i error
```

Expected: No errors

- [ ] **Step 9: Commit**

```bash
git add src/models/thread.rs src/models/mod.rs src/api/threads.rs src/api/mod.rs src/main.rs src/lib.rs
git commit -m "feat: add chat/threads API endpoints for task development"
```

---

### Task 14: Create Quadlet unit for Ardent Forge

**Files:**
- Create: `~/.config/systemd/user/ardent-forge.container`
- Create: `~/.config/systemd/user/ardent-forge-state.volume`

- [ ] **Step 1: Create container build**

```bash
cargo build --release 2>&1 | tail -5
```

Expected: Binary at `target/release/ardent_forge`

- [ ] **Step 2: Create OCI image (use podman directly for now)**

```bash
cat > Containerfile << 'EOF'
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
COPY target/release/ardent_forge /usr/local/bin/
RUN chmod +x /usr/local/bin/ardent_forge
EXPOSE 7030
CMD ["ardent_forge"]
EOF
```

- [ ] **Step 3: Build container image**

```bash
podman build -t ardent-forge:latest -f Containerfile .
```

Expected: Successfully built image

- [ ] **Step 4: Create Quadlet unit for Ardent Forge**

Create `~/.config/systemd/user/ardent-forge.container`:
```ini
[Unit]
Description=Ardent Forge Agentic Coding Control Plane
After=podman-network-default.network
Wants=network-online.target
StartLimitIntervalSec=0

[Container]
Image=ardent-forge:latest
ContainerName=ardent-forge
Network=default
PublishPort=127.0.0.1:7030:7030
Volume=%h/.local/share/ardent-forge:/data:z
EnvironmentFile=%d/run/agenix/anthropic-api-key
EnvironmentFile=%d/run/agenix/linear-api-key

[Service]
Type=notify
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target default.target
```

- [ ] **Step 5: Create volume for state**

Create `~/.config/systemd/user/ardent-forge-state.volume`:
```ini
[Unit]
Description=Ardent Forge Data Volume
PartOf=ardent-forge.service

[Volume]
VolumeName=ardent-forge-state

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 6: Enable and start service**

```bash
systemctl --user daemon-reload
systemctl --user enable ardent-forge.service
systemctl --user start ardent-forge.service
```

- [ ] **Step 7: Verify service is running**

```bash
systemctl --user status ardent-forge.service
curl http://localhost:7030/api/health
```

Expected: `ok` from curl

- [ ] **Step 8: Commit Containerfile and service definition**

```bash
git add Containerfile
git commit -m "feat: add containerfile and quadlet unit for ardent forge deployment"
```

---

### Task 15: Verify Ardent Forge Phase 2 complete

**Files:**
- None (verification only)

- [ ] **Step 1: Check binary builds**

```bash
cargo build --release 2>&1 | grep -i error | wc -l
```

Expected: 0 (no errors)

- [ ] **Step 2: Check API endpoints are accessible**

```bash
curl -s http://localhost:7030/api/health
curl -s http://localhost:7030/api/threads | jq .
```

Expected: `"ok"` and valid JSON

- [ ] **Step 3: List all features implemented**

Create `docs/phase2-complete.md`:
```markdown
# Phase 2: Ardent Forge Complete

## Features Implemented

- [x] Rust + Axum backend
- [x] Svelte 5 frontend (built into binary)
- [x] SQLite schema (tasks, threads, sessions, cost tracking)
- [x] Modular agent framework (Agent trait, stage gates)
- [x] Coordinator for task sequencing
- [x] Code and Plan agents (scaffolds)
- [x] Linear client and poller
- [x] Chat/Threads API endpoints (/api/threads/*, dispatch, messages)
- [x] Health check endpoint
- [x] Quadlet deployment unit
- [x] Binary serving frontend via Axum

## Next Steps (Phase 4+)

- [ ] Implement Claude Code session spawning in Code agent
- [ ] Implement SSE streaming for session events
- [ ] Implement Linear issue comment posting
- [ ] Add more agents (Scheduler, Reviewer, etc.)
- [ ] Add authentication/authorization
- [ ] Add cost tracking and metrics
```

- [ ] **Step 4: Final status**

```bash
git log --oneline | head -10
```

Expected: All commits from Phase 2 visible

- [ ] **Step 5: Document how to continue**

Create `docs/phase3-start.md`:
```markdown
# Phase 3: nb (Notebook) Implementation

After Phase 2 (Ardent Forge) is complete and deployed, start Phase 3.

## Starting Point

1. Create new Python repository: `~/Repos/github.com/t-eckert/nb`
2. Follow Phase 3 tasks in the implementation plan
3. Both Ardent Forge and nb will be independent applications on the same Homelab

## Shared Infrastructure

Both applications leverage:
- Homelab NixOS configuration (Quadlet, nftables, agenix)
- Ollama container (embeddings)
- Tailscale access
- Shared monitoring (Grafana, Prometheus, Loki)
```

---

## Phase 3: nb from Scratch (Python + FastAPI)

### Task 16: Initialize nb Python project

**Files:**
- Create: `~/Repos/github.com/t-eckert/nb/pyproject.toml`
- Create: `~/Repos/github.com/t-eckert/nb/uv.lock`
- Create: `~/Repos/github.com/t-eckert/nb/src/nb/__init__.py`
- Create: `~/Repos/github.com/t-eckert/nb/src/nb/main.py`

- [ ] **Step 1: Create nb repository**

```bash
cd ~/Repos/github.com/t-eckert
mkdir nb
cd nb
git init
touch README.md
git add README.md
git commit -m "init: create nb repository"
```

- [ ] **Step 2: Create pyproject.toml**

Create `pyproject.toml`:
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "nb"
version = "0.1.0"
description = "Personal knowledge management system with Zettelkasten agents"
requires-python = ">=3.13"
dependencies = [
    "fastapi==0.115.0",
    "uvicorn==0.30.0",
    "sqlalchemy==2.0.0",
    "aiosqlite==0.20.0",
    "anthropic==0.28.0",
    "gitpython==3.1.0",
    "pydantic==2.5.0",
    "pydantic-settings==2.1.0",
    "python-telegram-bot==21.2",
    "httpx==0.25.2",
]

[tool.hatch.build.targets.wheel]
packages = ["src/nb"]
```

- [ ] **Step 3: Initialize project structure**

```bash
mkdir -p src/nb tests
touch src/nb/__init__.py tests/__init__.py
```

- [ ] **Step 4: Create main.py**

Create `src/nb/main.py`:
```python
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("nb starting up")
    yield
    logger.info("nb shutting down")

app = FastAPI(title="nb", lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=7031)
```

- [ ] **Step 5: Create requirements.txt for local development**

```bash
uv pip compile pyproject.toml -o requirements.txt
```

- [ ] **Step 6: Test installation**

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
python -m nb.main
```

Expected: Server starts on port 7031

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/nb/__init__.py src/nb/main.py README.md
git commit -m "feat: initialize python project with fastapi scaffoldng"
```

---

### Task 17: Create SQLite schema for nb (FTS5 + vectors)

**Files:**
- Create: `src/nb/db.py`
- Create: `migrations/001_init.sql`

- [ ] **Step 1: Create database module**

Create `src/nb/db.py`:
```python
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "/tmp/nb.db"):
        self.db_path = Path(db_path)
        self.conn = None

    def connect(self):
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode = WAL")
        logger.info(f"Connected to database at {self.db_path}")

    def initialize(self):
        if not self.conn:
            self.connect()

        sql = (Path(__file__).parent.parent.parent / "migrations" / "001_init.sql").read_text()
        self.conn.executescript(sql)
        self.conn.commit()
        logger.info("Database initialized")

    def close(self):
        if self.conn:
            self.conn.close()

    def execute(self, sql: str, params=None):
        return self.conn.execute(sql, params or [])

    def commit(self):
        self.conn.commit()
```

- [ ] **Step 2: Create migrations directory and schema**

Create `migrations/001_init.sql`:
```sql
-- Notes table
CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    frontmatter TEXT,
    created_at DATETIME NOT NULL,
    modified_at DATETIME NOT NULL,
    git_commit_sha TEXT
);

-- Full-text search index (FTS5)
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    title,
    content,
    content=notes,
    content_rowid=rowid
);

-- Trigger to keep FTS index in sync
CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid, title, content) VALUES (new.rowid, new.title, new.content);
END;

CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, content) VALUES ('delete', old.rowid, old.title, old.content);
END;

CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, content) VALUES ('delete', old.rowid, old.title, old.content);
    INSERT INTO notes_fts(rowid, title, content) VALUES (new.rowid, new.title, new.content);
END;

-- Embeddings table (for vector search)
CREATE TABLE IF NOT EXISTS embeddings (
    id TEXT PRIMARY KEY,
    note_id TEXT NOT NULL UNIQUE REFERENCES notes(id),
    embedding BLOB NOT NULL,
    model_name TEXT NOT NULL,
    created_at DATETIME NOT NULL
);

-- Link graph (wikilinks and backlinks)
CREATE TABLE IF NOT EXISTS links (
    id TEXT PRIMARY KEY,
    from_path TEXT NOT NULL,
    to_path TEXT NOT NULL,
    link_text TEXT,
    created_at DATETIME NOT NULL,
    FOREIGN KEY(from_path) REFERENCES notes(path),
    FOREIGN KEY(to_path) REFERENCES notes(path)
);

-- Chat history (Telegram)
CREATE TABLE IF NOT EXISTS chat_turns (
    id TEXT PRIMARY KEY,
    user_message TEXT NOT NULL,
    assistant_response TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    tokens_in INTEGER,
    tokens_out INTEGER,
    cost_usd REAL
);

-- Proposals (agent-generated suggestions)
CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    agent_name TEXT NOT NULL,
    proposal_type TEXT NOT NULL,
    target_path TEXT,
    content TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at DATETIME NOT NULL,
    reviewed_at DATETIME,
    accepted BOOLEAN
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_notes_path ON notes(path);
CREATE INDEX IF NOT EXISTS idx_notes_created_at ON notes(created_at);
CREATE INDEX IF NOT EXISTS idx_embeddings_note_id ON embeddings(note_id);
CREATE INDEX IF NOT EXISTS idx_links_from_path ON links(from_path);
CREATE INDEX IF NOT EXISTS idx_links_to_path ON links(to_path);
CREATE INDEX IF NOT EXISTS idx_chat_turns_created_at ON chat_turns(created_at);
CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status);
CREATE INDEX IF NOT EXISTS idx_proposals_created_at ON proposals(created_at);
```

- [ ] **Step 3: Update main.py to initialize database**

Update `src/nb/main.py`:
```python
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from nb.db import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = Database()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("nb starting up")
    db.initialize()
    yield
    logger.info("nb shutting down")
    db.close()

app = FastAPI(title="nb", lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Test database initialization**

```bash
python -c "from nb.db import Database; db = Database(); db.initialize(); print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/nb/db.py migrations/001_init.sql src/nb/main.py
git commit -m "feat: add sqlite schema with fts5 and embeddings support"
```

---

### Task 18: Create vault integration (filesystem + Git)

**Files:**
- Create: `src/nb/vault.py`
- Create: `tests/test_vault.py`

- [ ] **Step 1: Create vault module**

Create `src/nb/vault.py`:
```python
import logging
from pathlib import Path
from git import Repo
import subprocess

logger = logging.getLogger(__name__)

class VaultManager:
    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self.repo = Repo(str(self.vault_path))

    def read_note(self, path: str) -> str:
        """Read a single note from the vault"""
        note_path = self.vault_path / path
        if not note_path.exists():
            raise FileNotFoundError(f"Note not found: {path}")
        return note_path.read_text()

    def write_note(self, path: str, content: str, message: str) -> None:
        """Write a note and commit"""
        note_path = self.vault_path / path
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(content)

        # Commit
        self.repo.index.add([str(note_path)])
        self.repo.index.commit(message)
        logger.info(f"Committed: {message}")

    def get_changed_files(self, since_commit: str = None) -> list[str]:
        """Get list of files changed since a commit"""
        if since_commit is None:
            since_commit = "HEAD~1"

        result = subprocess.run(
            ["git", "diff", "--name-only", since_commit, "HEAD"],
            cwd=self.vault_path,
            capture_output=True,
            text=True
        )

        return result.stdout.strip().split("\n") if result.stdout.strip() else []

    def pull_latest(self) -> None:
        """Pull latest changes from remote"""
        self.repo.remotes.origin.pull()
        logger.info("Pulled latest changes")

    def push_changes(self) -> None:
        """Push changes to remote"""
        self.repo.remotes.origin.push()
        logger.info("Pushed changes")
```

- [ ] **Step 2: Create test file**

Create `tests/test_vault.py`:
```python
import tempfile
from pathlib import Path
from git import Repo
from nb.vault import VaultManager

def test_read_note():
    """Test reading a note from the vault"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize a git repo
        repo = Repo.init(tmpdir)

        # Create a test note
        note_path = Path(tmpdir) / "test.md"
        note_path.write_text("# Test\n\nContent")
        repo.index.add([str(note_path)])
        repo.index.commit("initial")

        # Test read
        vault = VaultManager(tmpdir)
        content = vault.read_note("test.md")
        assert content == "# Test\n\nContent"

def test_write_note():
    """Test writing a note to the vault"""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Repo.init(tmpdir)

        vault = VaultManager(tmpdir)
        vault.write_note("test.md", "# New Note\n\nContent", "test: add note")

        # Verify it exists
        note_path = Path(tmpdir) / "test.md"
        assert note_path.exists()
        assert note_path.read_text() == "# New Note\n\nContent"
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_vault.py -v
```

Expected: 2 passed

- [ ] **Step 4: Update pyproject.toml with test dependency**

Update `pyproject.toml`:
```toml
[project.optional-dependencies]
dev = [
    "pytest==7.4.0",
    "pytest-asyncio==0.23.0",
]
```

- [ ] **Step 5: Commit**

```bash
git add src/nb/vault.py tests/test_vault.py pyproject.toml
git commit -m "feat: add vault manager for obsidian git integration"
```

---

### Task 19: Implement hybrid retrieval (FTS5 + semantic)

**Files:**
- Create: `src/nb/retrieval.py`
- Create: `tests/test_retrieval.py`

- [ ] **Step 1: Create retrieval module**

Create `src/nb/retrieval.py`:
```python
import logging
from typing import List, Tuple
from nb.db import Database

logger = logging.getLogger(__name__)

class HybridRetriever:
    def __init__(self, db: Database, k: int = 10):
        self.db = db
        self.k = k

    def search_fts(self, query: str) -> List[Tuple[str, float]]:
        """Full-text search using FTS5"""
        sql = """
            SELECT notes.path, 0 as rank
            FROM notes_fts
            JOIN notes ON notes_fts.rowid = notes.rowid
            WHERE notes_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """
        results = self.db.execute(sql, (query, self.k)).fetchall()
        return [(row[0], row[1]) for row in results]

    def search_semantic(self, embedding: List[float]) -> List[Tuple[str, float]]:
        """Semantic search using embeddings (placeholder)"""
        # TODO: Implement vector search once embeddings are populated
        logger.info("Semantic search not yet implemented")
        return []

    def hybrid_search(self, query: str) -> List[str]:
        """Hybrid search combining FTS and semantic"""
        fts_results = self.search_fts(query)

        # For now, just return FTS results
        # TODO: Combine with semantic search using RRF
        return [path for path, _ in fts_results]
```

- [ ] **Step 2: Create test file**

Create `tests/test_retrieval.py`:
```python
import tempfile
from pathlib import Path
from git import Repo
from nb.db import Database
from nb.retrieval import HybridRetriever

def test_hybrid_search():
    """Test hybrid search"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize vault
        repo = Repo.init(tmpdir)
        note_path = Path(tmpdir) / "test.md"
        note_path.write_text("# Machine Learning\n\nDeep learning concepts")
        repo.index.add([str(note_path)])
        repo.index.commit("initial")

        # Initialize database
        db = Database(f"{tmpdir}/nb.db")
        db.initialize()

        # Add note to database
        db.execute(
            """
            INSERT INTO notes (id, path, title, content, created_at, modified_at)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            ("note-1", "test.md", "Machine Learning", "# Machine Learning\n\nDeep learning concepts")
        )
        db.commit()

        # Test search
        retriever = HybridRetriever(db)
        results = retriever.hybrid_search("machine learning")

        assert len(results) == 1
        assert results[0] == "test.md"
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_retrieval.py -v
```

Expected: 1 passed

- [ ] **Step 4: Commit**

```bash
git add src/nb/retrieval.py tests/test_retrieval.py
git commit -m "feat: implement hybrid retrieval with fts5 and semantic search placeholders"
```

---

### Task 20: Create Librarian agent (orphan detection)

**Files:**
- Create: `src/nb/agents/__init__.py`
- Create: `src/nb/agents/librarian.py`
- Create: `tests/test_librarian.py`

- [ ] **Step 1: Create agents package**

Create `src/nb/agents/__init__.py`:
```python
"""Agent implementations for nb"""
```

- [ ] **Step 2: Implement Librarian agent**

Create `src/nb/agents/librarian.py`:
```python
import logging
from nb.db import Database

logger = logging.getLogger(__name__)

class Librarian:
    """Nightly maintenance agent: orphan detection, stale notes, tag normalization"""

    def __init__(self, db: Database):
        self.db = db

    async def detect_orphans(self) -> list[str]:
        """Find notes with no inbound or outbound links"""
        sql = """
            SELECT path FROM notes
            WHERE path NOT IN (SELECT DISTINCT from_path FROM links)
            AND path NOT IN (SELECT DISTINCT to_path FROM links)
        """
        results = self.db.execute(sql).fetchall()
        orphans = [row[0] for row in results]
        logger.info(f"Found {len(orphans)} orphan notes")
        return orphans

    async def detect_stale_notes(self, days: int = 180) -> list[str]:
        """Find notes untouched for N days that have inbound links"""
        sql = """
            SELECT DISTINCT notes.path
            FROM notes
            WHERE (julianday('now') - julianday(notes.modified_at)) > ?
            AND notes.path IN (SELECT to_path FROM links)
        """
        results = self.db.execute(sql, (days,)).fetchall()
        stale = [row[0] for row in results]
        logger.info(f"Found {len(stale)} stale notes")
        return stale

    async def run(self) -> dict:
        """Run nightly maintenance pass"""
        orphans = await self.detect_orphans()
        stale = await self.detect_stale_notes()

        logger.info(f"Librarian pass complete: {len(orphans)} orphans, {len(stale)} stale")

        return {
            "agent": "librarian",
            "orphans": orphans,
            "stale_notes": stale,
        }
```

- [ ] **Step 3: Create test**

Create `tests/test_librarian.py`:
```python
import tempfile
from pathlib import Path
from git import Repo
from nb.db import Database
from nb.agents.librarian import Librarian

@pytest.mark.asyncio
async def test_detect_orphans():
    """Test orphan detection"""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Repo.init(tmpdir)

        # Create test notes
        (Path(tmpdir) / "orphan.md").write_text("# Orphan\n\nNo links")
        (Path(tmpdir) / "linked.md").write_text("# Linked\n\n[[orphan]]")

        repo.index.add(["."])
        repo.index.commit("initial")

        # Initialize database
        db = Database(f"{tmpdir}/nb.db")
        db.initialize()

        # Add notes
        db.execute(
            """
            INSERT INTO notes (id, path, title, content, created_at, modified_at)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            ("note-1", "orphan.md", "Orphan", "# Orphan\n\nNo links")
        )
        db.execute(
            """
            INSERT INTO notes (id, path, title, content, created_at, modified_at)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            ("note-2", "linked.md", "Linked", "# Linked\n\n[[orphan]]")
        )
        db.execute(
            """
            INSERT INTO links (id, from_path, to_path, created_at)
            VALUES (?, ?, ?, datetime('now'))
            """,
            ("link-1", "linked.md", "orphan.md")
        )
        db.commit()

        # Test
        librarian = Librarian(db)
        orphans = await librarian.detect_orphans()

        # orphan.md has an inbound link, so it's not orphaned
        assert len(orphans) == 0
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_librarian.py -v
```

Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add src/nb/agents/__init__.py src/nb/agents/librarian.py tests/test_librarian.py
git commit -m "feat: implement librarian agent for orphan detection and maintenance"
```

---

### Task 21: Create Telegram adapter

**Files:**
- Create: `src/nb/adapters/__init__.py`
- Create: `src/nb/adapters/telegram.py`

- [ ] **Step 1: Create adapters package**

Create `src/nb/adapters/__init__.py`:
```python
"""Chat adapters for nb"""
```

- [ ] **Step 2: Implement Telegram adapter**

Create `src/nb/adapters/telegram.py`:
```python
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logger = logging.getLogger(__name__)

class TelegramAdapter:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.app = None

    async def start(self):
        """Start the Telegram bot"""
        self.app = Application.builder().token(self.bot_token).build()

        # Add handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        logger.info("Telegram bot started")

    async def stop(self):
        """Stop the Telegram bot"""
        if self.app:
            await self.app.stop()
            logger.info("Telegram bot stopped")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        await update.message.reply_text(
            "Welcome to nb! Send me a message to search your vault."
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming messages"""
        user_message = update.message.text
        logger.info(f"Received message: {user_message}")

        # TODO: Implement message processing with Companion agent
        await update.message.reply_text(f"You said: {user_message}")
```

- [ ] **Step 3: Update main.py to include Telegram**

Update `src/nb/main.py`:
```python
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from nb.db import Database
from nb.adapters.telegram import TelegramAdapter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = Database()
telegram_adapter = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("nb starting up")
    db.initialize()

    # Start Telegram adapter if token is provided
    import os
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if bot_token:
        global telegram_adapter
        telegram_adapter = TelegramAdapter(bot_token)
        await telegram_adapter.start()

    yield

    logger.info("nb shutting down")
    if telegram_adapter:
        await telegram_adapter.stop()
    db.close()

app = FastAPI(title="nb", lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Commit**

```bash
git add src/nb/adapters/__init__.py src/nb/adapters/telegram.py src/nb/main.py
git commit -m "feat: add telegram bot adapter for nb chat interface"
```

---

### Task 22: Create Quadlet unit for nb

**Files:**
- Create: `~/.config/systemd/user/nb.container`
- Create: `Containerfile.nb`

- [ ] **Step 1: Create Containerfile for nb**

Create `Containerfile.nb`:
```dockerfile
FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN pip install -e .
COPY . .
EXPOSE 7031
CMD ["uvicorn", "nb.main:app", "--host", "0.0.0.0", "--port", "7031"]
```

- [ ] **Step 2: Build nb image**

```bash
cd ~/Repos/github.com/t-eckert/nb
podman build -t nb:latest -f Containerfile.nb .
```

Expected: Successfully built image

- [ ] **Step 3: Create Quadlet unit for nb**

Create `~/.config/systemd/user/nb.container`:
```ini
[Unit]
Description=nb Personal Knowledge Management System
After=podman-network-default.network ollama.service
Wants=network-online.target
StartLimitIntervalSec=0

[Container]
Image=nb:latest
ContainerName=nb
Network=default
PublishPort=127.0.0.1:7031:7031
Volume=%h/.local/share/nb:/data:z
Volume=%h/Repos/github.com/t-eckert/notebook:/vault:z
EnvironmentFile=%d/run/agenix/anthropic-api-key
EnvironmentFile=%d/run/agenix/telegram-bot-token

[Service]
Type=notify
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target default.target
```

- [ ] **Step 4: Create data volume for nb**

Create `~/.config/systemd/user/nb-state.volume`:
```ini
[Unit]
Description=nb Data Volume
PartOf=nb.service

[Volume]
VolumeName=nb-state

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 5: Enable and start service**

```bash
systemctl --user daemon-reload
systemctl --user enable nb.service
systemctl --user start nb.service
```

- [ ] **Step 6: Verify service**

```bash
systemctl --user status nb.service
curl http://localhost:7031/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 7: Commit**

```bash
git add Containerfile.nb
git commit -m "feat: add containerfile and quadlet unit for nb deployment"
```

---

## Phase 4+: Agent Refinement (Ongoing)

The implementation plan for phases 4 onwards is outlined in the code comments and GitHub issues. Key items to address incrementally:

- [ ] Implement Companion agent for conversational Telegram interactions
- [ ] Implement Researcher agent for ingest pipeline (PDF → literature notes)
- [ ] Integrate Ollama embeddings into retrieval
- [ ] Add Claude API integration for agent decision-making
- [ ] Implement cost tracking and metrics in both systems
- [ ] Add monitoring and alerting (Grafana, Prometheus, Loki, Tempo)
- [ ] Test end-to-end workflows (Linear issue → Ardent Forge execution)
- [ ] Test end-to-end vault enrichment (Telegram message → nb proposal)

---

## Summary

This plan takes you from zero to a working two-system architecture on Homelab in approximately 3-4 weeks of focused work:

**Week 1-2:** Homelab infrastructure (Quadlet, Podman, Ollama, nftables, agenix)
**Week 2-3:** Ardent Forge from scratch (Rust + Axum + Svelte 5, single binary)
**Week 3-4:** nb from scratch (Python + FastAPI, vault integration, Librarian agent, Telegram)
**Week 4+:** Iterative agent development and refinement

Each task is small enough to complete in a single focused session (2-5 minutes per step).
