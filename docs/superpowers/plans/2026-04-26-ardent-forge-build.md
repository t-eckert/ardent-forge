# Ardent Forge (Rust + Axum) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Ardent Forge as a standalone Rust service with single-binary deployment: Linear task polling → agent-driven task execution → chat/threads interface for task development.

**Architecture:** Single Rust binary (Axum web server + Svelte 5 frontend compiled into dist/) with embedded SQLite database. Agent framework (Code, Plan) with connector/tool registry. Linear poller continuously syncs issues into task queue. REST API for tasks/threads/chat. Session orchestration spawns Claude Code invocations in sandboxed project containers.

**Tech Stack:** Rust 1.75+, Axum (async web), Tokio (async runtime), SQLite (WAL), Svelte 5 + SvelteKit, TypeScript, Tailwind CSS 4

---

### Task 1: Initialize Rust Project and SQLite Schema

**Files:**
- Create: `Cargo.toml`
- Create: `src/main.rs`
- Create: `src/lib.rs`
- Create: `src/db.rs`
- Create: `src/models.rs`
- Create: `migrations/001_initial.sql`

- [ ] **Step 1: Create Cargo.toml**

```toml
[package]
name = "ardent-forge"
version = "0.1.0"
edition = "2021"

[[bin]]
name = "ardent-forge"
path = "src/main.rs"

[dependencies]
axum = "0.7"
tokio = { version = "1", features = ["full"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
sqlx = { version = "0.7", features = ["runtime-tokio-native-tls", "sqlite"] }
tower = "0.4"
tower-http = { version = "0.5", features = ["fs", "trace"] }
tracing = "0.1"
tracing-subscriber = "0.3"
chrono = { version = "0.4", features = ["serde"] }
ulid = "1.1"
uuid = { version = "1.0", features = ["v4", "serde"] }
futures = "0.3"
anyhow = "1.0"
thiserror = "1.0"

[profile.release]
opt-level = 3
lto = true
```

- [ ] **Step 2: Create src/main.rs**

```rust
use axum::{
    extract::State,
    routing::{get, post},
    Router, Json,
};
use sqlx::sqlite::SqlitePoolOptions;
use std::sync::Arc;
use tower_http::fs::ServeDir;
use tracing_subscriber;

mod db;
mod models;
mod agents;
mod connectors;
mod coordinator;
mod api;

#[derive(Clone)]
pub struct AppState {
    db: sqlx::SqlitePool,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();

    let database_url = std::env::var("DATABASE_URL")
        .unwrap_or_else(|_| "sqlite://ardent-forge.db".to_string());

    let pool = SqlitePoolOptions::new()
        .max_connections(5)
        .connect(&database_url)
        .await?;

    sqlx::migrate!("./migrations")
        .run(&pool)
        .await?;

    let state = AppState { db: pool };

    let app = Router::new()
        .route("/api/health", get(api::health))
        .route("/api/tasks", get(api::tasks::list_tasks))
        .route("/api/tasks", post(api::tasks::create_task))
        .route("/api/threads", get(api::threads::list_threads))
        .route("/api/threads/:id/messages", get(api::threads::get_thread_messages))
        .route("/api/threads/:id/messages", post(api::threads::post_message))
        .fallback_service(ServeDir::new("dist"))
        .with_state(state);

    let listener = tokio::net::TcpListener::bind("0.0.0.0:7030").await?;
    tracing::info!("Server listening on 0.0.0.0:7030");

    axum::serve(listener, app).await?;

    Ok(())
}
```

- [ ] **Step 3: Create src/lib.rs**

```rust
pub mod db;
pub mod models;
pub mod agents;
pub mod connectors;
pub mod coordinator;
pub mod api;

pub use db::AppState;
```

- [ ] **Step 4: Create src/models.rs**

```rust
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::FromRow;

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct Task {
    pub id: String,
    pub title: String,
    pub description: String,
    pub state: String, // queued, triaging, executing, verifying, delivering, completed, failed
    pub source: String, // linear, chat
    pub linear_issue_id: Option<String>,
    pub thread_id: Option<String>,
    pub result: Option<String>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct Thread {
    pub id: String,
    pub title: String,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct ThreadMessage {
    pub id: String,
    pub thread_id: String,
    pub content: String,
    pub message_type: String, // text, widget, task-dispatched, task-resolved
    pub metadata: Option<String>, // JSON for rich metadata
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateTaskRequest {
    pub title: String,
    pub description: String,
    pub source: String,
    pub linear_issue_id: Option<String>,
    pub thread_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PostMessageRequest {
    pub content: String,
    pub message_type: String,
    pub metadata: Option<serde_json::Value>,
}
```

- [ ] **Step 5: Create migrations/001_initial.sql**

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'queued',
    source TEXT NOT NULL,
    linear_issue_id TEXT,
    thread_id TEXT,
    result TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS thread_messages (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    content TEXT NOT NULL,
    message_type TEXT NOT NULL,
    metadata TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (thread_id) REFERENCES threads(id)
);

CREATE INDEX IF NOT EXISTS idx_tasks_state ON tasks(state);
CREATE INDEX IF NOT EXISTS idx_tasks_source ON tasks(source);
CREATE INDEX IF NOT EXISTS idx_thread_messages_thread_id ON thread_messages(thread_id);
```

- [ ] **Step 6: Create src/db.rs**

```rust
use sqlx::SqlitePool;

#[derive(Clone)]
pub struct AppState {
    pub db: SqlitePool,
}

impl AppState {
    pub async fn new(database_url: &str) -> anyhow::Result<Self> {
        let pool = sqlx::sqlite::SqlitePoolOptions::new()
            .max_connections(5)
            .connect(database_url)
            .await?;

        sqlx::migrate!("./migrations")
            .run(&pool)
            .await?;

        Ok(Self { db: pool })
    }
}
```

- [ ] **Step 7: Create stub modules and commit**

```bash
mkdir -p src/{agents,connectors,coordinator,api/tasks,api/threads}
touch src/agents.rs src/connectors.rs src/coordinator.rs
mkdir -p src/api && touch src/api/mod.rs src/api/health.rs src/api/tasks.rs src/api/threads.rs
mkdir -p migrations

# Add to src/agents.rs
echo "pub struct CodeAgent; pub struct PlanAgent;" > src/agents.rs

# Add to src/api/mod.rs
echo "pub mod health; pub mod tasks; pub mod threads;
pub async fn health() -> &'static str { \"OK\" }" > src/api/mod.rs

git add .
git commit -m "feat: initialize rust project with sqlx schema"
```

---

### Task 2: Implement REST API for Tasks

**Files:**
- Modify: `src/api/tasks.rs`
- Modify: `src/main.rs` (routes)

- [ ] **Step 1: Write tasks API**

```rust
// src/api/tasks.rs
use axum::{
    extract::{Path, State},
    http::StatusCode,
    Json,
};
use sqlx::Row;
use crate::{models::{CreateTaskRequest, Task}, AppState};

pub async fn list_tasks(
    State(state): State<AppState>,
) -> Result<Json<Vec<Task>>, StatusCode> {
    let tasks = sqlx::query_as::<_, Task>(
        "SELECT id, title, description, state, source, linear_issue_id, thread_id, result, created_at, updated_at FROM tasks ORDER BY created_at DESC"
    )
    .fetch_all(&state.db)
    .await
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(tasks))
}

pub async fn create_task(
    State(state): State<AppState>,
    Json(req): Json<CreateTaskRequest>,
) -> Result<Json<Task>, StatusCode> {
    let id = ulid::Ulid::new().to_string();
    let now = chrono::Utc::now();

    let task = Task {
        id: id.clone(),
        title: req.title,
        description: req.description,
        state: "queued".to_string(),
        source: req.source,
        linear_issue_id: req.linear_issue_id,
        thread_id: req.thread_id,
        result: None,
        created_at: now,
        updated_at: now,
    };

    sqlx::query(
        "INSERT INTO tasks (id, title, description, state, source, linear_issue_id, thread_id, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    .bind(&task.id)
    .bind(&task.title)
    .bind(&task.description)
    .bind(&task.state)
    .bind(&task.source)
    .bind(&task.linear_issue_id)
    .bind(&task.thread_id)
    .bind(&task.created_at)
    .bind(&task.updated_at)
    .execute(&state.db)
    .await
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(task))
}
```

- [ ] **Step 2: Commit**

```bash
git add src/api/tasks.rs
git commit -m "feat: implement tasks list and create endpoints"
```

---

### Task 3: Implement REST API for Threads and Messages

**Files:**
- Modify: `src/api/threads.rs`

- [ ] **Step 1: Write threads API**

```rust
// src/api/threads.rs
use axum::{
    extract::{Path, State},
    http::StatusCode,
    Json,
};
use crate::{models::{PostMessageRequest, Thread, ThreadMessage}, AppState};

pub async fn list_threads(
    State(state): State<AppState>,
) -> Result<Json<Vec<Thread>>, StatusCode> {
    let threads = sqlx::query_as::<_, Thread>(
        "SELECT id, title, created_at, updated_at FROM threads ORDER BY created_at DESC"
    )
    .fetch_all(&state.db)
    .await
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(threads))
}

pub async fn get_thread_messages(
    State(state): State<AppState>,
    Path(thread_id): Path<String>,
) -> Result<Json<Vec<ThreadMessage>>, StatusCode> {
    let messages = sqlx::query_as::<_, ThreadMessage>(
        "SELECT id, thread_id, content, message_type, metadata, created_at FROM thread_messages WHERE thread_id = ? ORDER BY created_at ASC"
    )
    .bind(&thread_id)
    .fetch_all(&state.db)
    .await
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(messages))
}

pub async fn post_message(
    State(state): State<AppState>,
    Path(thread_id): Path<String>,
    Json(req): Json<PostMessageRequest>,
) -> Result<Json<ThreadMessage>, StatusCode> {
    let id = ulid::Ulid::new().to_string();
    let now = chrono::Utc::now();

    let metadata_str = req.metadata.map(|m| m.to_string());

    let msg = ThreadMessage {
        id: id.clone(),
        thread_id: thread_id.clone(),
        content: req.content,
        message_type: req.message_type,
        metadata: metadata_str.clone(),
        created_at: now,
    };

    sqlx::query(
        "INSERT INTO thread_messages (id, thread_id, content, message_type, metadata, created_at)
         VALUES (?, ?, ?, ?, ?, ?)"
    )
    .bind(&msg.id)
    .bind(&msg.thread_id)
    .bind(&msg.content)
    .bind(&msg.message_type)
    .bind(&metadata_str)
    .bind(&msg.created_at)
    .execute(&state.db)
    .await
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(msg))
}
```

- [ ] **Step 2: Commit**

```bash
git add src/api/threads.rs
git commit -m "feat: implement threads and messages endpoints"
```

---

### Task 4: Initialize Svelte 5 Frontend

**Files:**
- Create: `ui/package.json`
- Create: `ui/svelte.config.js`
- Create: `ui/tsconfig.json`
- Create: `ui/vite.config.ts`
- Create: `ui/src/routes/+page.svelte`
- Create: `ui/src/lib/api.ts`

- [ ] **Step 1: Initialize pnpm project**

```bash
cd ui
npm create vite@latest . -- --template svelte
# Select: ✓ Svelte, ✓ TypeScript
pnpm install
pnpm add -D tailwindcss postcss autoprefixer @tailwindcss/typography
pnpm add bits-ui phosphor-svelte cva clsx tailwind-merge
```

- [ ] **Step 2: Create vite.config.ts**

```typescript
import { defineConfig } from 'vite'
import { svelte } from 'vite-plugin-svelte'

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

- [ ] **Step 3: Create UI API client**

```typescript
// ui/src/lib/api.ts
const API_BASE = process.env.NODE_ENV === 'development' 
  ? '/api'
  : '/api';

export async function getTasks() {
  const res = await fetch(`${API_BASE}/tasks`);
  return res.json();
}

export async function createTask(title: string, description: string, source: string) {
  const res = await fetch(`${API_BASE}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, description, source }),
  });
  return res.json();
}

export async function getThreads() {
  const res = await fetch(`${API_BASE}/threads`);
  return res.json();
}

export async function getThreadMessages(threadId: string) {
  const res = await fetch(`${API_BASE}/threads/${threadId}/messages`);
  return res.json();
}

export async function postThreadMessage(threadId: string, content: string, type: string) {
  const res = await fetch(`${API_BASE}/threads/${threadId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, message_type: type }),
  });
  return res.json();
}
```

- [ ] **Step 4: Create basic home page**

```svelte
<!-- ui/src/routes/+page.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { getTasks } from '../lib/api';

  let tasks: any[] = [];
  let loading = true;

  onMount(async () => {
    try {
      tasks = await getTasks();
    } catch (e) {
      console.error('Failed to load tasks:', e);
    }
    loading = false;
  });
</script>

<div class="p-8 max-w-4xl mx-auto">
  <h1 class="text-4xl font-bold mb-4">Ardent Forge</h1>
  
  {#if loading}
    <p>Loading...</p>
  {:else if tasks.length === 0}
    <p class="text-gray-500">No tasks yet</p>
  {:else}
    <div class="space-y-4">
      {#each tasks as task}
        <div class="border border-gray-200 rounded-lg p-4">
          <h2 class="font-semibold">{task.title}</h2>
          <p class="text-sm text-gray-600">{task.description}</p>
          <div class="mt-2 flex gap-2">
            <span class="text-xs bg-gray-100 px-2 py-1 rounded">{task.state}</span>
            <span class="text-xs bg-blue-100 px-2 py-1 rounded">{task.source}</span>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
```

- [ ] **Step 5: Build frontend and commit**

```bash
cd ui
pnpm build
cd ..
git add ui/ dist/
git commit -m "feat: initialize svelte 5 frontend and build"
```

---

### Task 5: Create Agent Framework Structure

**Files:**
- Create: `src/agents/mod.rs`
- Create: `src/agents/code.rs`
- Create: `src/agents/plan.rs`
- Create: `src/connectors/mod.rs`
- Create: `src/coordinator.rs`

- [ ] **Step 1: Write agent trait**

```rust
// src/agents/mod.rs
use async_trait::async_trait;
use crate::models::Task;

#[async_trait]
pub trait Agent: Send + Sync {
    fn name(&self) -> &str;
    fn stages(&self) -> Vec<&str>;
    async fn triage(&self, task: &Task) -> anyhow::Result<bool>;
    async fn execute(&self, task: &Task) -> anyhow::Result<serde_json::Value>;
    async fn verify(&self, task: &Task) -> anyhow::Result<bool>;
    async fn deliver(&self, task: &Task) -> anyhow::Result<()>;
}

pub mod code;
pub mod plan;

pub use code::CodeAgent;
pub use plan::PlanAgent;
```

Add `async-trait = "0.1"` to Cargo.toml

- [ ] **Step 2: Write CodeAgent stub**

```rust
// src/agents/code.rs
use async_trait::async_trait;
use crate::models::Task;
use super::Agent;

pub struct CodeAgent;

#[async_trait]
impl Agent for CodeAgent {
    fn name(&self) -> &str { "Code" }

    fn stages(&self) -> Vec<&str> {
        vec!["triage", "execute", "verify", "deliver"]
    }

    async fn triage(&self, _task: &Task) -> anyhow::Result<bool> {
        Ok(true) // Accept all tasks for now
    }

    async fn execute(&self, task: &Task) -> anyhow::Result<serde_json::Value> {
        tracing::info!("CodeAgent executing task: {}", task.id);
        // Placeholder: will invoke Claude Code in next task
        Ok(serde_json::json!({ "status": "pending" }))
    }

    async fn verify(&self, _task: &Task) -> anyhow::Result<bool> {
        Ok(true)
    }

    async fn deliver(&self, task: &Task) -> anyhow::Result<()> {
        tracing::info!("CodeAgent delivered task: {}", task.id);
        Ok(())
    }
}
```

- [ ] **Step 3: Write PlanAgent stub**

```rust
// src/agents/plan.rs
use async_trait::async_trait;
use crate::models::Task;
use super::Agent;

pub struct PlanAgent;

#[async_trait]
impl Agent for PlanAgent {
    fn name(&self) -> &str { "Plan" }

    fn stages(&self) -> Vec<&str> {
        vec!["verify"]
    }

    async fn triage(&self, _task: &Task) -> anyhow::Result<bool> {
        Ok(false) // Plan agent only verifies
    }

    async fn execute(&self, _task: &Task) -> anyhow::Result<serde_json::Value> {
        Err(anyhow::anyhow!("Plan agent does not execute"))
    }

    async fn verify(&self, _task: &Task) -> anyhow::Result<bool> {
        Ok(true)
    }

    async fn deliver(&self, _task: &Task) -> anyhow::Result<()> {
        Ok(())
    }
}
```

- [ ] **Step 4: Write connectors module**

```rust
// src/connectors/mod.rs
use serde_json::Value;
use std::collections::HashMap;

pub type ToolRegistry = HashMap<String, Box<dyn Fn(&str) -> anyhow::Result<Value> + Send + Sync>>;

pub fn default_registry() -> ToolRegistry {
    let mut registry = ToolRegistry::new();
    // Tools will be registered here in future tasks
    registry
}
```

- [ ] **Step 5: Write coordinator**

```rust
// src/coordinator.rs
use crate::{agents::Agent, models::Task, AppState};
use std::sync::Arc;

pub struct Coordinator {
    agents: Vec<Arc<dyn Agent>>,
}

impl Coordinator {
    pub fn new(agents: Vec<Arc<dyn Agent>>) -> Self {
        Self { agents }
    }

    pub async fn process_task(&self, state: &AppState, task: &Task) -> anyhow::Result<()> {
        tracing::info!("Coordinator processing task: {}", task.id);

        // Triage
        for agent in &self.agents {
            if agent.stages().contains(&"triage") {
                let should_process = agent.triage(task).await?;
                if should_process {
                    let result = agent.execute(task).await?;
                    sqlx::query("UPDATE tasks SET result = ? WHERE id = ?")
                        .bind(serde_json::to_string(&result)?)
                        .bind(&task.id)
                        .execute(&state.db)
                        .await?;
                }
            }
        }

        Ok(())
    }
}
```

- [ ] **Step 6: Commit**

```bash
git add src/agents/ src/connectors/ src/coordinator.rs
git commit -m "feat: implement agent framework and coordinator"
```

---

### Task 6: Create Quadlet Container Definition

**Files:**
- Create: `Quadlet.container`

- [ ] **Step 1: Write Quadlet container definition**

```ini
# Quadlet.container
[Unit]
Description=Ardent Forge (Code + Chat)
After=network.target
Wants=network.target

[Container]
Image=localhost/ardent-forge:latest
ContainerName=ardent-forge
Publish=7030:7030
Volume=%h/.config/ardent-forge/state:/app/data:Z
Volume=%h/.config/ardent-forge/projects:/projects:Z
Environment=DATABASE_URL=sqlite:///app/data/ardent-forge.db
Environment=RUST_LOG=info

[Install]
WantedBy=multi-user.target default.target
```

- [ ] **Step 2: Create Dockerfile**

```dockerfile
# Dockerfile
FROM rust:1.75 as builder
WORKDIR /build
COPY . .
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /build/target/release/ardent-forge /usr/local/bin/
COPY --from=builder /build/dist /app/dist
WORKDIR /app
EXPOSE 7030
CMD ["ardent-forge"]
```

- [ ] **Step 3: Create .dockerignore**

```
target/
dist/
.git
.gitignore
ui/node_modules
ui/.svelte-kit
```

- [ ] **Step 4: Commit**

```bash
git add Quadlet.container Dockerfile .dockerignore
git commit -m "feat: add docker and quadlet configuration"
```

---

### Task 7: Implement Basic Linear Integration

**Files:**
- Create: `src/linear/mod.rs`
- Create: `src/linear/client.rs`
- Create: `src/linear/poller.rs`

- [ ] **Step 1: Write Linear client**

```rust
// src/linear/client.rs
pub struct LinearClient {
    api_key: String,
}

impl LinearClient {
    pub fn new(api_key: String) -> Self {
        Self { api_key }
    }

    pub async fn fetch_issues(&self) -> anyhow::Result<Vec<LinearIssue>> {
        // Placeholder: will implement GraphQL query in next phase
        Ok(vec![])
    }

    pub async fn post_comment(&self, issue_id: &str, comment: &str) -> anyhow::Result<()> {
        // Placeholder
        Ok(())
    }
}

#[derive(Debug, Clone, serde::Deserialize)]
pub struct LinearIssue {
    pub id: String,
    pub title: String,
    pub description: Option<String>,
}
```

- [ ] **Step 2: Write Linear poller**

```rust
// src/linear/poller.rs
use super::LinearClient;
use crate::AppState;

pub async fn poll_linear(state: &AppState, client: &LinearClient) -> anyhow::Result<()> {
    let _issues = client.fetch_issues().await?;
    // Will implement task creation from issues in next phase
    Ok(())
}
```

- [ ] **Step 3: Create Linear module**

```rust
// src/linear/mod.rs
pub mod client;
pub mod poller;

pub use client::LinearClient;
pub use poller::poll_linear;
```

- [ ] **Step 4: Add to main and commit**

```rust
// Add to src/main.rs
mod linear;

// Add environment var loading
let linear_api_key = std::env::var("LINEAR_API_KEY").ok();
// Will integrate polling loop in next task
```

```bash
git add src/linear/
git commit -m "feat: add linear client and poller skeleton"
```

---

### Task 8: Implement Task Polling Loop

**Files:**
- Modify: `src/main.rs`
- Create: `src/background.rs`

- [ ] **Step 1: Write background task runner**

```rust
// src/background.rs
use crate::{AppState, agents::{CodeAgent, PlanAgent}, coordinator::Coordinator, linear::LinearClient};
use std::sync::Arc;
use tokio::time::{interval, Duration};

pub async fn start_background_tasks(state: AppState, linear_api_key: Option<String>) {
    let state_clone = state.clone();
    
    // Task processing loop
    tokio::spawn(async move {
        let agents: Vec<Arc<dyn crate::agents::Agent>> = vec![
            Arc::new(CodeAgent),
            Arc::new(PlanAgent),
        ];
        let coordinator = Coordinator::new(agents);
        let mut ticker = interval(Duration::from_secs(5));

        loop {
            ticker.tick().await;
            
            if let Ok(tasks) = sqlx::query_as::<_, crate::models::Task>(
                "SELECT * FROM tasks WHERE state = 'queued' LIMIT 1"
            )
            .fetch_optional(&state_clone.db)
            .await
            {
                if let Ok(Some(task)) = tasks {
                    tracing::info!("Processing task: {}", task.id);
                    let _ = coordinator.process_task(&state_clone, &task).await;
                }
            }
        }
    });

    // Linear polling loop (if API key provided)
    if let Some(key) = linear_api_key {
        let state_clone = state.clone();
        
        tokio::spawn(async move {
            let client = LinearClient::new(key);
            let mut ticker = interval(Duration::from_secs(60));

            loop {
                ticker.tick().await;
                if let Err(e) = crate::linear::poll_linear(&state_clone, &client).await {
                    tracing::error!("Linear polling error: {}", e);
                }
            }
        });
    }
}
```

- [ ] **Step 2: Update main.rs to start background tasks**

```rust
// In main.rs, after creating app state:
let linear_api_key = std::env::var("LINEAR_API_KEY").ok();
start_background_tasks(state.clone(), linear_api_key).await;
```

- [ ] **Step 3: Add to lib.rs**

```rust
// In src/lib.rs
pub mod background;
```

- [ ] **Step 4: Commit**

```bash
git add src/background.rs src/main.rs src/lib.rs
git commit -m "feat: add background task polling and processing loop"
```

---

### Task 9: Build and Test

**Files:**
- (no new files)

- [ ] **Step 1: Build Rust project**

```bash
cargo build --release
```

Expected: Compiles successfully, binary at `target/release/ardent-forge`

- [ ] **Step 2: Build frontend**

```bash
cd ui && pnpm build && cd ..
```

Expected: `dist/` directory created with static assets

- [ ] **Step 3: Test basic endpoints**

```bash
DATABASE_URL="sqlite://test.db" cargo run --release &
sleep 2
curl http://localhost:7030/api/health
# Expected: OK

curl -X POST http://localhost:7030/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"title":"Test","description":"Test task","source":"chat"}'
# Expected: 200 with task JSON

curl http://localhost:7030/api/tasks
# Expected: 200 with array containing created task

kill %1
```

- [ ] **Step 4: Commit final state**

```bash
git add .
git commit -m "build: ardent forge compiles and serves api + frontend"
git log --oneline | head -10
# Should show all implementation commits
```

---

**Next Steps:**

Ardent Forge binary is now functional with basic REST API, agent framework skeleton, and Linear integration scaffolding. Ready for:
1. Claude Code integration in CodeAgent
2. Enhanced Linear polling with actual issue→task conversion
3. Deployment via Homelab Quadlet
