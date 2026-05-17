IMPORTANT: I don't want to build exactly this anymore. We need to modify it significantly.



# Ardent Forge: A Design Study for a Self-Hosted Agentic Development Platform

## Executive Summary

Ardent Forge is a web-based control plane for running AI coding agents (Claude Code, Codex, etc.) inside Podman containers on a NixOS homelab. This document synthesizes a deep survey of the sandbox/agent-harness ecosystem (Sculptor, container-use, Conductor, Crystal, Claude Squad, claude-code-sandbox, Docker Sandboxes, E2B, and others), the Linux sandboxing primitive landscape (user namespaces, seccomp, SELinux, capabilities, network egress), the NixOS-specific container runtime story (Quadlet, rootless Podman, nix2container), and concrete control-plane patterns (streaming via SSE vs WebSocket, session state machines, intervention models, auth for a solo operator), and concludes with a specific recommended architecture.

The headline recommendations are:

1. **One long-lived rootless-Podman container per project**, but treat it as *rebuildable cattle, not pets*. Make `forge rebuild` a one-command operation.
2. **Git worktrees inside that single project container** (managed by Ardent Forge) for parallelism, not container-per-session. This is cheaper than Sculptor's container-per-agent model and sufficient for a single user.
3. **Use `--userns=keep-id` with the same UID as the host** and bind-mount the project directory at the same path — this matches the user's stated ergonomics and avoids the file-ownership nightmares that plague naive rootless setups.
4. **Network egress allowlist via nftables + a local CoreDNS/Blocky with an explicit allowlist** is the highest-ROI defense beyond the container boundary. Anthropic's devcontainer `init-firewall.sh` is the best reference; replicate its policy, not its implementation.
5. **Control plane in Rust (axum + SQLite), frontend in Svelte 5, streaming over SSE, agent invocation via `podman exec` of `claude --output-format stream-json`** parsed into a structured event bus. This is the simplest stack that scales to "dozens of sessions" without any actual scaling.
6. **Tailscale for access, no additional auth layer.** For a solo operator accessing their own homelab, this is both the most secure *and* the most ergonomic choice.
7. **Quadlet-nix for declarative Podman units** — the user already lives in Nix, and this is 2026's clear winner over the older `virtualisation.oci-containers` module.

The remainder of this report covers each area in depth with specific tradeoffs, citations, and traps to avoid.

---

## 1. Container Sandboxing for AI Coding Agents: Deep Survey

### 1.1 Anthropic's Own Guidance

Anthropic ships two sandboxing stories, and conflating them is a common mistake:

- **The Claude Code devcontainer reference** ([code.claude.com/docs/en/devcontainer](https://code.claude.com/docs/en/devcontainer)) isolates Claude Code from the host. It uses a `devcontainer.json`, a `Dockerfile`, and `init-firewall.sh` that implements a **default-deny outbound policy** with an allowlist for npm, GitHub, Anthropic API, sentry, and statsig. It is designed specifically to make `claude --dangerously-skip-permissions` safe(r) for unattended operation ([source](https://code.claude.com/docs/en/devcontainer)).
- **The native `sandbox` feature** ([code.claude.com/docs/en/sandboxing](https://code.claude.com/docs/en/sandboxing)) is different — it's an in-process sandbox using `@anthropic-ai/sandbox-runtime` (bubblewrap on Linux) that isolates *the Bash tool only*, not Edit/Write/etc. Community filings note that "the sandbox only applies to Bash" and that Edit-based attacks are not prevented ([source](https://github.com/anthropics/claude-code/issues/26616)).

Both are **explicit about their limitations**: "When executed with --dangerously-skip-permissions, devcontainers don't prevent a malicious project from exfiltrating anything accessible in the devcontainer including Claude Code credentials. We recommend only using devcontainers when developing with trusted repositories" ([source](https://code.claude.com/docs/en/devcontainer)). This phrasing is important: the container is a blast-radius limiter for your own agent going wild, not a sandbox for untrusted code from the internet.

### 1.2 Open-Source Agent Harnesses — Comparative Summary

| Project | Parallelism Model | Isolation | Notable | Source |
|---|---|---|---|---|
| **Sculptor (Imbue)** | Container per agent + worktree | Docker | "Pairing Mode" bidirectional sync; no network isolation by default | [github.com/imbue-ai/sculptor](https://github.com/imbue-ai/sculptor) |
| **container-use (Dagger)** | Container per environment, via MCP | Dagger-built containers + per-agent git branch | MCP server protocol; `cu stdio`; git-branch review workflow | [github.com/dagger/container-use](https://github.com/dagger/container-use) |
| **Conductor (conductor.build)** | Worktree per session, Mac app | None (host processes) | Uses Claude Code SDK; Linear integration | [conductor.build](https://www.conductor.build/) |
| **Crystal/Nimbalyst** | Worktree per session, Electron | None | xterm.js in Electron, SQLite-backed session store | [github.com/stravu/crystal](https://github.com/stravu/crystal) |
| **Claude Squad** | tmux + worktree | None | TUI, supports Aider/Codex/Gemini, `--autoyes` | [github.com/smtg-ai/claude-squad](https://github.com/smtg-ai/claude-squad) |
| **claude-code-sandbox (textcortex)** | Container per session | Docker, optional Podman | Browser terminal, auto-PR | [github.com/textcortex/claude-code-sandbox](https://github.com/textcortex/claude-code-sandbox) |
| **claudebox (RchGrav)** | Container per project | Docker | Pre-configured language profiles | [github.com/RchGrav/claudebox](https://github.com/RchGrav/claudebox) |
| **trailofbits/claude-code-devcontainer** | Devcontainer CLI | Docker (Colima on Mac) | Firewall script + chattr +i hardening; built for security audits | [github.com/trailofbits/claude-code-devcontainer](https://github.com/trailofbits/claude-code-devcontainer) |
| **Docker Sandboxes (`sbx`)** | Fresh microVM per invocation | **microVM** (Linux KVM via Docker VMM) | Only mainstream product offering true microVM isolation for local agent execution | [docker.com/blog/docker-sandboxes](https://www.docker.com/blog/docker-sandboxes-run-claude-code-and-other-coding-agents-unsupervised-but-safely/) |
| **E2B** | Cloud Firecracker microVM | microVM | Cloud-only; not appropriate for local homelab | [e2b.dev](https://e2b.dev/) |

**Sculptor deserves specific attention** because it pioneered the container-per-agent pattern and shares many motivations with Ardent Forge. Their docs (["Each task = one isolated container"](https://docs.imbue.com/features/containers)) are explicit: every agent gets its own container with a *copy of the repo*, and "Pairing Mode" syncs a chosen container's state back to the host ([source](https://docs.imbue.com/features/containers)). They added dev-container support specifically to amortize the startup cost of per-task containers — "agent setup time dropped from minutes to seconds" with cached images ([source](https://imbue.com/product/containers/)). They explicitly acknowledge: "Network isolation is up to you (right now.) We plan to make it easier to restrict network access to particular agents, but right now the containers have full access" ([source](https://github.com/imbue-ai/sculptor)).

**container-use is the most architecturally interesting** because it's the only serious project that exposes the container sandbox as an **MCP tool set the agent calls into** rather than a runtime the agent runs inside. Each agent call creates "a fresh container in its own git branch" with full command-history logging, terminal-attach for intervention, and `git checkout <branch_name>` for review ([source](https://github.com/dagger/container-use)). It's Dagger-powered, so the container environment is programmatically defined rather than a static image. For Ardent Forge, the relevant insight is not to copy the MCP-server shape (which pushes the sandbox decision into the agent's tool-call loop), but the review-via-branches idea.

**Conductor's** design is Mac-only and runs agents directly on the host (no container), isolating only via worktrees. Their docs are explicit about using the Claude Code SDK rather than the CLI ([source](https://elite-ai-assisted-coding.dev/p/the-parallel-agent-multiplier-conductor-with-charlie-holtz)). For a Linux homelab, the Mac-app part doesn't transfer; the worktree pattern does.

### 1.3 Devcontainer-Based Approaches

VS Code devcontainers and the [Dev Container Spec](https://containers.dev) are the *de facto* standard and are what Anthropic's reference uses. Tools worth knowing:

- **`@devcontainers/cli`** lets you start devcontainers without VS Code; the user can `devcontainer up` and then `devcontainer exec claude` from any terminal emulator, which is the standard pattern for SSH-first workflows ([source](https://mitjamartini.com/posts/claude-code-in-devcontainer/)).
- **Features composition** (the `ghcr.io/anthropics/devcontainer-features/claude-code:1.0` feature, for example) lets you layer language toolchains declaratively ([source](https://nakamasato.medium.com/using-claude-code-safely-with-dev-containers-b46b8fedbca9)).
- **Traps**: VS Code's devcontainer architecture injects IPC sockets and env vars into the container by design, which agents can use to escape back to the host environment. The claude-code-devcontainer community notes that VS Code automatically runs pytest inside the container "to figure out what tests are available, which loads fixtures, which can cause agent-generated code to run while you are in Pairing Mode" ([source](https://github.com/imbue-ai/sculptor) — Sculptor's security notes). Running `claude` inside a container *without* the VS Code IPC attached (e.g., `devcontainer exec`, or Ardent Forge's direct `podman exec`) sidesteps this.

For Ardent Forge, the value of devcontainer format isn't VS Code — it's **reusing the spec as the per-project configuration surface**. If a project has a `.devcontainer/devcontainer.json` with `features`, Ardent Forge can honor it, giving the user Codespaces-compatible definitions without tying them to VS Code.

### 1.4 Firecracker / microVM / gVisor: When Are They Worth It?

**Firecracker-based (E2B, Modal, Morph, Docker Sandboxes) and Kata Containers** provide a hardware-virtualized boundary: a real KVM guest kernel sits between the agent and the host. Firecracker boots in ~125 ms with ~5 MiB overhead ([source](https://memo.d.foundation/breakdown/e2b)), which makes it viable for per-task sandboxes in a way traditional VMs never were. This is what Docker's new `sbx` product uses: "Docker Sandboxes now run on dedicated microVMs, adding a hard security boundary" ([source](https://www.docker.com/blog/docker-sandboxes-run-claude-code-and-other-coding-agents-unsupervised-but-safely/)).

**gVisor** (`runsc`) intercepts syscalls in userspace, giving you a distinct kernel implementation between the container and the host. It has two structural downsides: semantic differences from real Linux ("not as optimized as more mature implementations" — [gVisor docs](https://gvisor.dev/docs/architecture_guide/performance/)) and performance overhead for I/O-heavy workloads. A USENIX HotCloud'19 paper measured "opening and closing files on an external tmpfs is 216× slower" and "reading small files is 11× slower" on gVisor ([source](https://www.usenix.org/system/files/hotcloud19-paper-young.pdf)). VFS2/LISAFS improvements have since closed this gap substantially ([source](https://cloud.google.com/blog/products/containers-kubernetes/gvisor-file-system-improvements-for-gke-and-serverless)), but a dev container doing `npm install`/`cargo build` will still feel it.

**When are they worth the complexity?**

- **Multi-tenant services (third parties running agents on your infra)**: yes, microVM is the right call; E2B/Docker Sandboxes/Modal all made this choice for a reason.
- **Untrusted code (arbitrary code execution sandbox for end-users)**: yes, same.
- **Single-user homelab running your own agents on your own code**: **no**. The threat model is "Claude goes wild and deletes my ~/.ssh" or "a malicious npm postinstall I pulled in tries to exfiltrate secrets." Rootless Podman + a network egress allowlist + no credential mounts covers both. The added operational complexity of running Kata or Firecracker on bare metal is substantial (you're on x86 with KVM, which is fine, but quadlet + microVM isn't a well-trodden path).

**The honest rule**: reach for microVMs when you can't trust the agent's runtime *at all*, which is not the situation for a senior engineer running their own agent on their own code on their own hardware.

### 1.5 Rootless Podman vs Rootless Docker vs Docker Desktop

On Linux, the practical comparison is:

- **Rootless Podman** is the default-correct choice. Daemonless, no setuid daemon, native user-namespace mapping, first-class SELinux integration, first-class systemd integration via Quadlet. The downsides are real but mostly quality-of-life: storage duplication if you also run rootful, NFS/GPFS unsupported for storage ([Podman docs](https://github.com/containers/podman/blob/main/docs/tutorials/rootless_tutorial.md)), and the occasional permission weirdness from subuid-mapped file ownership ([source](https://blog.nviso.eu/2026/02/03/rootless-containers-with-podman/)).
- **Rootless Docker** works but carries the daemon design (`dockerd-rootless.sh`) as baggage. The `.sock` is still effectively a root-in-container endpoint within the user's namespace.
- **Docker Desktop on Linux** runs Docker inside a VM on Linux just as it does on macOS. For a homelab server accessed via SSH, this is all downside.
- **A subtle trap**: Dan Walsh (Podman maintainer) notes that *two* rootless containers run **in the same user namespace** and can attack each other from a userns perspective — `podman run --userns=auto` as rootful actually isolates containers from each other better ([source](https://github.com/containers/podman/discussions/13728)). For a single-user setup where all containers belong to you, this is fine; worth knowing if you later want multiple humans sharing the box.

**Verdict**: Rootless Podman + Quadlet is the right default. Use `--userns=keep-id` when bind-mounting project directories (explained next).

---

## 2. Concrete Sandboxing Primitives on Linux

### 2.1 User Namespaces and UID Mapping

Podman supports several `--userns` modes ([Red Hat](https://www.redhat.com/en/blog/rootless-podman-user-namespace-modes)):

- **Default (rootless)**: The user's host UID maps to UID 0 inside the container; the container's subuid range (e.g. `johndoe:100000:65536`) handles everything else.
- **`keep-id`**: Maps the host user's UID to the *same* UID inside the container. Files created by the agent inside bind-mounted directories are owned by the host user on the host with no chown dance.
- **`auto`**: Each container gets a unique, non-overlapping subuid range — strictly better isolation between containers but breaks shared caches.
- **`nomap`**: Host UID is not mapped at all.

**For Ardent Forge's stated design (project dir bind-mounted at same path, shared caches, clean host file ownership), `--userns=keep-id` is exactly the right choice.** With `keep-id`, a `cargo build` inside the container writes `target/` owned by the host user, and a subsequent `rg` on the host works without `sudo`.

The **tradeoff**: the agent's "UID 0" privileges inside the container are still your host user's privileges for bind-mounted paths. If `~/.ssh` is ever bind-mounted, the agent can read it as cleanly as you can. This is fine as long as you never mount those paths (see 2.8).

Subuid/subgid setup on NixOS with `users.users.<name>.autoSubUidGidRange = true` (when using quadlet-nix) handles the ranges declaratively ([source](https://github.com/SEIAROTg/quadlet-nix)).

### 2.2 Seccomp Profiles

Podman's default seccomp profile blocks ~44 syscalls out of ~300+ and is moderately protective ([Docker docs, same policy](https://docs.docker.com/engine/security/seccomp/)). For a dev agent, the default is **almost certainly sufficient** and tightening it further is unlikely to catch real threats while likely to break tools. Specifically:

- Containers building Rust/Node toolchains legitimately need lots of syscalls (`ptrace` for strace-like tools, `unshare` for language-runtime sandboxes, etc.).
- Custom profiles are a well-known source of breakage; Podman's own history is littered with "requested action matches default action of filter" regressions ([source](https://github.com/containers/podman/issues/11883)).

**Recommendation**: Stick with the default seccomp profile. Only write a custom profile if a specific capability is being used as an attack vector and you have evidence. Podman's eBPF-based profile generator (`oci-seccomp-bpf-hook`) exists for building minimal profiles from an observed run ([source](https://podman.io/blogs/2019/10/15/generate-seccomp-profiles.html)), but it's overkill here.

### 2.3 SELinux / AppArmor on NixOS

NixOS ships with AppArmor support (`security.apparmor`), not SELinux by default. For a single-user homelab:

- Podman applies SELinux labels automatically when SELinux is enforcing (its `:Z` / `:z` mount option does relabeling). On non-SELinux systems (which NixOS is, by default), those options are no-ops.
- AppArmor is useful primarily for system services, not for dev containers where the profile would be extremely permissive anyway.

**Recommendation**: Don't enable SELinux on NixOS for this. The effort-to-defense ratio is bad; your time is better spent on the network egress allowlist (§2.5).

### 2.4 Capabilities

Podman by default drops all capabilities except a small set (`CAP_SETUID`, `CAP_SETGID`, `CAP_NET_BIND_SERVICE`, `CAP_CHOWN`, etc.). For a dev container, you mostly want to:

- **Keep `NET_ADMIN` and `NET_RAW` dropped** (they are, by default). Several Claude-sandbox wrappers add these back to make `iptables` work inside the container for the firewall init script ([example](https://github.com/StefanMaron/claudeCodeAlDevContainer)). **Don't do that in Ardent Forge.** Put the egress control on the host (nftables) instead — it's more robust and doesn't require giving the container network-privileged capabilities.
- **Explicitly `--cap-drop=ALL --cap-add=<only what you need>`** for the dev container. A typical set for a build-and-test workload is empty; language toolchains don't need Linux capabilities.

### 2.5 Network Egress Control

This is the **single highest-leverage security control** beyond the container boundary, and it's where Anthropic's devcontainer does the most work. The reference `init-firewall.sh` implements **default-deny outbound** with an allowlist for npm, GitHub, Anthropic API, sentry, and statsig ([source](https://code.claude.com/docs/en/devcontainer)).

Design options for Ardent Forge:

1. **Host-level nftables** per container (matching on the container's veth/IP). Most robust, doesn't require capabilities in the container, survives container restarts. Needs scripting in the Quadlet unit's `ExecStartPost`/`ExecStopPost`.
2. **CNI network policies** (Podman supports the netavark backend with `network_admin`). Harder to reason about than raw nftables on a single-user box.
3. **Egress proxy** (Squid or mitmproxy with TLS MITM). Useful if you want to *inspect* traffic, not just allow/deny. Adds operational complexity.
4. **DNS-level blocking** (Blocky, Pi-hole, CoreDNS policy). Complements but does not replace IP-level filtering — agents that hard-code IPs bypass it.

**A sensible allowlist** for a Rust+Go+Python+TS dev agent:

- `*.crates.io`, `static.crates.io`, `index.crates.io`, `crates.io`
- `*.npmjs.org`, `registry.npmjs.org`, `*.npmjs.com`
- `*.pypi.org`, `pypi.org`, `files.pythonhosted.org`
- `proxy.golang.org`, `sum.golang.org`, `index.golang.org`
- `github.com`, `*.github.com`, `*.githubusercontent.com`, `objects.githubusercontent.com`, `codeload.github.com`, `api.github.com`, `ghcr.io`
- `api.anthropic.com`, `statsig.anthropic.com`, `sentry.anthropic.com`
- `registry-1.docker.io`, `auth.docker.io`, `*.cloudflare.docker.com` (only if the container pulls images; usually not needed)

Put the list in a Nix-generated nftables set; iterate the list as the host-side policy, not inside the container.

**Trap**: Data exfiltration via DNS (TXT records, subdomain encoding) still works through any DNS resolver you allow. For a single-user threat model this is overkill to worry about; for enterprise it isn't.

### 2.6 Mount Strategies

Three kinds of mounts should be distinguished:

- **Project bind mount**: `-v ${HOME}/code/project:/home/you/code/project`. Same path host and container; `keep-id` makes ownership work. This is the user's chosen design and it's correct.
- **Shared caches (read-write)**: `~/.cargo/registry`, `~/.cache/go-build`, `~/.npm`, `~/.local/share/pnpm/store/v3`. Mount these **read-write, shared across all project containers**. This is a big perf win over per-project caches and is what Sculptor added dev-container support to approximate ([source](https://imbue.com/product/containers/)). Risk: a compromised cache (e.g., a planted crate) persists across containers. Mitigation: these are already trusted content from the agent's perspective; the upstream-registry attack surface is the same whether cached or not.
- **Named volumes**: for the agent's own state (`~/.claude` inside the container). Use a named Podman volume per project so `forge rebuild` doesn't wipe OAuth tokens. This is the pattern `sbox` uses: "The entire .claude folder is synced to .sbox/claude-cache/ when running sbox stop" ([source](https://github.com/streamingfast/sbox)).

**Read-only vs RW guidance**:

- Project directory: RW (obviously).
- Language caches: RW.
- Claude config/credentials (mounted from host): **Avoid entirely**. See §2.7.
- Dotfiles (bash/zsh history, `.gitconfig` minus credentials): RO bind mount of a curated subset, or better: generate these inside the image from declarative config.

### 2.7 Protecting Host Secrets

**Never mount into the agent container**:

- `~/.ssh` (private keys)
- `~/.aws/credentials`, `~/.aws/config`
- `~/.config/gh` (GitHub CLI tokens)
- `~/.kube/config` (cluster creds)
- `~/.docker/config.json` (registry creds)
- `~/.gnupg`
- Any agenix-decrypted path, any sops-nix path
- The Podman socket itself (see §7.2)
- `/var/run/docker.sock` (goes without saying, but: one wrapper project, sbox, notes "allowUnixSockets can inadvertently grant access to powerful system services... allowing access to /var/run/docker.sock would effectively grant access to the host system" — [source](https://code.claude.com/docs/en/sandboxing))

**Patterns for scoped credential injection** when the agent legitimately needs them:

- **GitHub fine-grained PATs** scoped to the specific repo. Inject as env var at session start, not baked into the image. The trailofbits devcontainer does this: `export CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-... devc rebuild # rebuilds with token` ([source](https://github.com/trailofbits/claude-code-devcontainer)).
- **Short-lived cloud creds** via `aws sts assume-role` on the host, pass as env vars with short TTL.
- **Anthropic API key** — inject from a secret store (agenix) at container start; never bind-mount the decrypted file path.
- **SSH-for-git-push**: use HTTPS + a scoped PAT, not SSH. This keeps your actual SSH key out of the container entirely.

---

## 3. Container Image Strategy

### 3.1 Options and Tradeoffs

**Nix-built OCI images (`dockerTools.buildLayeredImage`, `nix2container`)**:

- Pros: reproducible, precise dependency tracking, excellent layer reuse across images that share Nix store paths, no from-scratch RUN brittleness.
- Cons: Nix package names ≠ npm/pypi names; some tools have weak or stale Nix derivations; cache locality is good *within* your own ecosystem but layers don't deduplicate with Debian-based images elsewhere.
- Size comparison from community benchmarks: a `cowsay` image was 107 MB with Nix vs 48 MB with Alpine ([source](https://emilio.co.za/blog/nix-oci-images-macos/)), largely because Nix pulls full glibc and coreutils. For a multi-hundred-MB dev image with Rust toolchains, the Nix overhead is relatively smaller.
- `nix2container` specifically is worth knowing: it's "archive-less", doesn't write tarballs to the Nix store, and lets you skip already-pushed layers ([source](https://github.com/nlewo/nix2container)). Faster iteration than `dockerTools.buildImage`.

**Traditional Dockerfiles**:

- Pros: Documented everywhere; AI agents know this format; familiar layer semantics.
- Cons: Non-reproducible (floating `apt-get update`, base image tag drift); not integrated with the user's Nix flake.

**Devcontainer features composition** (`ghcr.io/anthropics/devcontainer-features/claude-code:1.0`):

- Pros: Standard format; multiple language toolchains compose (Rust + Node + Python + Go) without you writing each install step.
- Cons: Features are Debian-focused; slower than Nix's evaluation-time layer optimization.

**Hybrid: Nix-built base + per-project Dockerfile overlay**:

- Pros: Base layer is reproducible and shared; project-specific setup is easy to customize.
- Cons: Two build systems to maintain.

### 3.2 Multi-Language Projects

A realistic Ardent Forge project container for a senior engineer needs Rust (stable + nightly), Node (via fnm/volta/nvm or pinned), Python (uv), Go, ripgrep, fd, jq, git, jj, GitHub CLI (but no auth), and probably Docker/Podman CLI (for docker-compose workloads). The devcontainer-features model is genuinely good here; the Nix model is *better* if you're already writing flakes.

### 3.3 Base Image Choice

For a **dev** container specifically:

- **Debian/Ubuntu**: default-correct; what `mcr.microsoft.com/devcontainers/base:ubuntu` uses. Broadest toolchain compatibility.
- **Alpine**: smaller, but `musl` vs `glibc` bites you regularly with pre-built binaries (ruff, node-sass, etc.). Don't use it as the dev base.
- **Distroless / Wolfi**: for production runtime images, not dev. A dev container without `bash` is a bad dev container.
- **NixOS-as-container**: viable if you want the full Nix experience inside the container; in practice the Nix-built minimal image approach (where `/nix/store` is the layer but the OS is stripped) is what works.

**Recommendation**: Debian base for the first iteration (devcontainer-features composable), migrate to Nix-built layered image later if image build time becomes annoying.

---

## 4. Long-Lived Project Containers vs Ephemeral Task Containers

### 4.1 How Other Projects Handle It

- **Sculptor**: ephemeral (container per task), but with cached dev-container base for fast spin-up. Each agent gets its own container with a copy of the repo; "Sculptor auto-cleans up its images and containers on a cadence" ([source](https://github.com/imbue-ai/sculptor)).
- **container-use**: ephemeral (container per environment + branch).
- **Conductor / Crystal / Claude Squad**: no containers at all — worktree-per-session on the host with tmux or child processes.
- **claude-code-sandbox (per-session container)**: ephemeral per session, but persists volumes across sessions.
- **claudebox, trailofbits/claude-code-devcontainer, sbox**: long-lived (per-project or per-workspace) container; the agent is `docker exec`'d in.

The industry split is real. Ephemeral-per-task is genuinely more hygienic from a security and reproducibility perspective; long-lived-per-project is genuinely better for IDE warm caches, LSP state, and filesystem/build state continuity. Sculptor explicitly pays the "minutes to seconds" cost of per-task containers through dev-container caching ([source](https://imbue.com/product/containers/)).

### 4.2 Tradeoffs for Ardent Forge's Stated Design

The user has chosen **long-lived per project**, which is the right call for the stated setup because:

- **Incremental build state**: Rust `target/` alone is 5-30 GB for large projects. Rebuilding from scratch per task is not merely slow, it's hostile.
- **LSP/language-server warm state**: rust-analyzer's in-memory index takes 60+ seconds to warm on a medium project. If Ardent Forge later runs an LSP inside the container to enrich the agent's context, restart cost is prohibitive.
- **Dev servers / watchers**: `next dev`, `cargo watch`, `uvicorn --reload` — all meaningful to keep running between tasks.
- **Security hygiene concern**: a long-lived container accumulates installed packages, mutated config, stale processes. The mitigation is making `forge rebuild <project>` a one-command op that tears down and restarts the container from the image with caches preserved.

### 4.3 Git Worktree Patterns Inside the Container

**The critical architectural choice**: when the user wants to run N parallel agent sessions on the same project, do they want N containers or N worktrees in one container?

Analysis favors **worktrees in one container**:

- A single host/container can run N agents on N worktrees trivially; tmux and Claude Squad both do this.
- Worktrees share the `.git` object store, so disk cost is the working tree only (the Cursor forum measured 9.82 GB for a 20-minute session on a 2 GB codebase with automatic worktree creation — [source](https://devcenter.upsun.com/posts/git-worktrees-for-parallel-ai-coding-agents/); for disciplined use, it's fine).
- Worktrees share the same language-cache state (cargo target, node_modules, etc.) *per worktree*. For Rust, set `CARGO_TARGET_DIR=~/.cache/cargo-target` to share across worktrees ([source](https://dev.to/recca0120/git-worktree-multiple-working-directories-per-repo-and-the-key-to-parallel-ai-agents-40)). For Node, pnpm's content-addressable store handles this naturally.
- Worktrees do NOT isolate runtime state — ports, databases, shared services. This is a known structural gap; pragmatically, the user's agent sessions are unlikely to all bind port 3000 simultaneously, but it's worth being aware of.

**The flip side** (container-per-session, Sculptor's model) buys you:

- Independent runtime state (each agent can `cargo run` without port conflicts).
- Independent package installs (`apt install` inside the container without racing another agent).
- Stronger isolation if one agent gets malicious or broken.

**For Ardent Forge's single-user case, worktrees in one long-lived container is the right starting point.** It gives you parallelism for free without the container-multiplication cost. If the runtime-state problem bites, you can escalate to per-worktree sub-containers (or just run `next dev` on different ports per worktree).

### 4.4 Reset/Rebuild Semantics

Make `forge rebuild <project>` a first-class operation that:

1. Stops and removes the container (keeps named volumes).
2. Rebuilds the image (if Dockerfile/flake changed).
3. Recreates the container with the same volume mounts and config.
4. Optionally runs a `setupCommands`-style init (like devcontainer's).

Do NOT use `podman checkpoint` / CRIU for this. It works in principle but is fragile in practice and adds a restore path that's harder to reason about than "rebuild from image."

### 4.5 Long-Running Processes Across Host Reboots

Ardent Forge itself is a Quadlet systemd unit; it comes back on reboot. The project containers are also Quadlet units with `autoStart = true`; they come back too. The agent *sessions* within them do not automatically resume — Claude Code's own `/resume` handles this when the user re-attaches to a session. Ardent Forge should track session state in SQLite (next section) so the UI can show "session X was running when host rebooted, click to resume via `claude --resume`".

Dev servers and watchers started inside the container by the agent are trickier. Two options: (a) the agent spawns them as child processes that die with the container (common, correct) and restarts them after reboot explicitly, or (b) systemd-inside-container supervises them (complex, probably overkill).

---

## 5. Ardent Forge Control Plane Architecture

### 5.1 Session Modeling

An **agent session** is a first-class entity with:

- `id` (UUID), `project_id`, `worktree_path`, `branch`, `prompt`, `created_at`, `state` (enum).
- `state` state machine: `queued → starting → running → waiting_for_input → running → (idle) → done | failed | cancelled`.
- `pid` (of the `claude`/`codex` process inside the container).
- `claude_session_id` (from `SDKSystemMessage` — needed for `claude --resume`).
- Transcript: store the raw `stream-json` events (newline-delimited JSON) in a file per session, plus a parsed summary in SQLite for list/search queries.
- Resumability after crash: on startup, Ardent Forge reconciles its DB against running containers (`podman ps --format json`) and against `ps -eo pid` inside each container to find orphaned agent processes. Lost sessions go to `unknown` state, which the UI surfaces with a "reconnect" action.

This is basically the pattern Crystal uses — "SQLite state, agent spawning, and the API" — but for a web UI ([source](https://github.com/stravu/crystal/blob/main/CLAUDE.md)).

### 5.2 Streaming Agent Output

**Format**: The Claude Code SDK emits newline-delimited JSON via `--output-format stream-json --include-partial-messages --verbose`. Event types include `message_start`, `content_block_start` (text or tool_use), `content_block_delta` (`text_delta`, `input_json_delta`, `thinking_delta`), `content_block_stop`, `message_stop`, plus higher-level `AssistantMessage` and `ResultMessage` envelopes ([source](https://platform.claude.com/docs/en/agent-sdk/streaming-output), [source](https://theouterloop.substack.com/p/a-few-fun-things-you-can-do-with)).

**Transport choice: SSE, WebSockets, or long-polling?**

- **SSE (Server-Sent Events)**: one-way server→client, trivially proxyable through reverse proxies, auto-reconnect on disconnect via `Last-Event-ID`. Matches the shape of the Claude Code stream perfectly — you're reformatting NDJSON from the CLI as SSE frames. **This is the right default.**
- **WebSockets**: needed if the client needs a persistent bidirectional channel, e.g. for xterm.js terminal input. Use for the terminal-attach feature but not for the main event stream.
- **Long-polling**: only if you hit proxy/load-balancer hostility. Not relevant on a homelab.

**Backpressure and long outputs**: A single agent session can produce many MB of events. Architecture:

1. The `podman exec claude ...` subprocess writes NDJSON to stdout.
2. A per-session goroutine/task in Ardent Forge reads, parses, and **persists** each event to an append-only file (`sessions/<id>.jsonl`) and to SQLite (parsed projection).
3. Connected clients subscribe via SSE; the subscriber starts from `Last-Event-ID` if replaying, or "tail" if live.
4. SQLite stores only the structured projection (tool calls, text segments, token usage, cost). The raw JSONL is the source of truth.

This separation is important: the SQLite-or-Postgres-for-transcripts question is a **false dichotomy**. Store events as JSONL on disk (truly append-only, grep-friendly, cheap), and use SQLite for indices/queries (session list, active count, time ranges, cost rollups). Postgres is overkill for one user.

### 5.3 Intervention Patterns

Claude Code itself offers these intervention primitives, which Ardent Forge should expose:

- **Inject a new user message mid-loop**: supported natively by Claude Code when the process is running; the CLI accepts input over stdin in interactive mode. In headless streaming mode you pass messages through the SDK's `send_message` or by restarting with `--resume <session_id>` + new prompt.
- **Pause/resume**: Claude Code doesn't have a true pause; `SIGSTOP` on the process works but is crude. The proper pattern is to let the current tool call complete, then gate the next with a permission prompt (which Ardent Forge can hold).
- **Kill**: `SIGTERM` then `SIGKILL` on the `claude` process inside the container.
- **Approve a gated tool call**: this is what the permissions system is for. If you run *without* `--dangerously-skip-permissions`, Claude asks per tool; Ardent Forge can surface these as approvals in the UI. The user has chosen to run with `--dangerously-skip-permissions` (container = sandbox), so this is mostly moot, but it's worth supporting for specific high-risk tools via hooks (`PreToolUse` validator — see `bash_command_validator_example.sh` pattern noted in [mitjamartini's post](https://mitjamartini.com/posts/claude-code-in-devcontainer/)).

Sculptor, Conductor, and Claude Code's own UI all basically wrap these primitives. The interesting one is **forking** from mid-session — "spin off a new agent from any point in your session history" ([Sculptor roadmap](https://imbue.com/sculptor-announce/)). Since you have the raw JSONL transcript, fork = new session with context seeded from a truncated replay. Worth building once the basic flow works.

### 5.4 Multiplexing

For N sessions:

- UI shows a list with per-session state, current tool call, last-activity time, and a "needs attention" flag (true when state is `waiting_for_input` or has an approval pending).
- Desktop notifications via Web Push (works over HTTPS + service worker) or via an ntfy.sh self-hosted push service (easier).
- A "top" view that shows all sessions in a grid, with truncated streaming output per tile.

Crystal does something like this in a desktop app with xterm.js per session ([source](https://deepwiki.com/stravu/crystal)); for a web UI, the same pattern works.

### 5.5 Persistence Layer

- **SQLite (WAL mode)**: one file at `~/.local/share/ardent-forge/state.db`. Tables for projects, sessions, session_events (projection only), settings, preauth keys, permission_grants. Rusqlite+tokio or sqlx.
- **Transcript JSONL**: `~/.local/share/ardent-forge/sessions/<id>.jsonl`. Append-only, rotated/compressed after N days.
- **Postgres**: don't. Single user, no HA requirements, SQLite's concurrency model (WAL + multiple readers + one writer) is plenty.

### 5.6 Frontend

Svelte 5 + SvelteKit is a good fit. Specific patterns:

- **xterm.js for terminal view**: when the user "drops into" a session to intervene, open a WebSocket to Ardent Forge that proxies to `podman exec -it <container> bash` (via a PTY). Use `@xterm/xterm` + `@xterm/addon-attach` + `@xterm/addon-fit` ([reference](https://www.qovery.com/blog/react-xtermjs-a-react-library-to-build-terminals)).
- **Diff viewer**: Monaco's diff editor (via `monaco-editor` ESM) or the lighter `diff2html`. For tool-call-specific UI: render `Edit` as a diff, `Write` as a new-file panel, `Bash` as a terminal-style block.
- **Tool-call components**: one component per known tool (`Bash`, `Edit`, `Read`, `Glob`, `Grep`, `TodoWrite`, `WebFetch`, etc.), each consuming the matching `content_block_start → stop` pair. Falls back to a generic JSON viewer for unknown tools.
- **Streaming rendering**: treat each session as a reactive store; the component subscribes to the SSE event feed and appends events. Svelte 5 runes (`$state.raw` for the transcript to avoid deep reactivity cost) handle this well.

### 5.7 Auth for a Solo Operator

This is the question where "sensible default" genuinely exists: **Tailscale + no application auth**.

Reasoning:

- Tailscale's WireGuard mesh is already the user's SSH transport; Ardent Forge piggybacks on it. The attack surface is one service (tailscaled) with a strong security track record, not two.
- An HTTP service bound to the Tailscale interface (100.x.y.z) and not to 0.0.0.0 is unreachable except from authenticated Tailscale nodes. Tag-based ACLs (`tag:personal`) can further restrict which devices in your tailnet reach it.
- No password management, no session cookies to worry about compromise, no MFA flows to build.

Alternatives and when you'd pick them:

- **Authelia/Authentik**: you already run SSO for other services, want LDAP/OIDC upstream, occasionally share access with others.
- **Cloudflare Access**: you want public-internet reachability with zero-trust auth; means your dev sessions transit Cloudflare.
- **Basic auth**: genuinely worse than Tailscale on every axis for this use case.
- **Headscale**: self-hosted Tailscale control server, worth knowing about but adds ops burden without much benefit for a solo user ([github.com/juanfont/headscale](https://github.com/juanfont/headscale)).

**Recommendation**: Tailscale, bind service to the tailnet interface, no auth in the app. Add a single-token API key mechanism for machine access (Linear webhook, CLI from another laptop) that's not on the tailnet.

### 5.8 How Ardent Forge Invokes the Agent

Three viable patterns:

1. **Fresh `podman exec` per session**: `podman exec -w /home/you/code/project/.worktrees/session-abc <container> claude -p "<prompt>" --output-format stream-json --include-partial-messages --verbose --dangerously-skip-permissions`. Subprocess is owned by Ardent Forge; stream is piped back. Simple. Agent state lives in the container's `/home/you/.claude` volume.
2. **Agent daemon inside the container**: Ardent Forge talks to a long-running Go/Rust process inside the container over a Unix socket bind-mounted to the host. Reduces per-session startup overhead; complicates deployment (need a supervisor in the container).
3. **MCP server model** (container-use's approach): the agent runs on the host, calls into the container via MCP tools. Breaks the "agent in sandbox" invariant; not what Ardent Forge wants.

**Recommendation**: Start with #1 (`podman exec` per session). Claude Code's startup is ~2 seconds; not worth the daemon complexity until you have evidence of a problem. If the user ever moves to stateless per-task containers, then the daemon becomes more interesting.

The command shape specifically:

```bash
podman exec -i \
  -w "$WORKTREE" \
  -e ANTHROPIC_API_KEY="$SCOPED_KEY" \
  "$CONTAINER" \
  claude -p "$PROMPT" \
    --output-format stream-json \
    --include-partial-messages \
    --verbose \
    --dangerously-skip-permissions \
    --resume "$CLAUDE_SESSION_ID"  # only for resumption
```

Parse NDJSON from stdout, tee to `sessions/<id>.jsonl`, broadcast parsed events over SSE.

---

## 6. Prior Art: Concrete Summaries

### Sculptor (Imbue)
- **Architecture**: Electron desktop app (Mac/Linux/WSL). One Docker container per agent, each with a full repo clone. "Pairing Mode" bidirectionally syncs an agent's container state to a local git worktree for IDE editing ([source](https://imbue.com/sculptor/)).
- **Why they chose it**: isolation per agent eliminates package conflicts and enables true parallel code execution.
- **Open source status**: The main Sculptor repo is on GitHub (`imbue-ai/sculptor`) but the product is described as "in closed development" with open-source ecosystem as roadmap ([source](https://imbue.com/sculptor/)).
- **Notable limitation**: "containers have full access" — no network isolation by default.
- **Relevance to Ardent Forge**: establishes the design pattern, but per-agent containers are more than a single-user homelab needs.

### container-use (Dagger)
- **Architecture**: MCP server (`container-use stdio`). Exposes `environment_create`, `environment_run`, etc. as tools an MCP-compatible agent (Claude Code, Cursor, Goose) can call. Each environment = one Dagger-composed container + one git branch.
- **Review workflow**: `git checkout <branch_name>` on the host to review any agent's work. Commands and logs are recorded for audit.
- **Source**: [github.com/dagger/container-use](https://github.com/dagger/container-use); docs at [container-use.com](https://container-use.com/).
- **Relevance**: the "one container per branch, review via git" pattern informs Ardent Forge's worktree+branch-per-session model even if Ardent Forge doesn't go MCP-server.

### Conductor (conductor.build)
- **Architecture**: Mac-only Electron-ish app. Uses the Claude Code SDK (not the CLI) for fine control. Each workspace is a git worktree; no container.
- **Interesting**: the presenter notes it uses "the Claude Code SDK, which is a wrapper on the CLI" and runs commands in TypeScript ([source](https://elite-ai-assisted-coding.dev/p/the-parallel-agent-multiplier-conductor-with-charlie-holtz)).
- **Linear integration** is in-roadmap/shipped; this is the workflow pattern the user wants to replicate for their own Linear setup.
- **Relevance**: validates worktree-per-session; no container means weaker isolation than Ardent Forge targets.

### Crystal (now Nimbalyst)
- **Architecture**: Electron (main process + renderer), SQLite state, xterm.js terminal, Bull task queue ([source](https://github.com/stravu/crystal/blob/main/CLAUDE.md)). Worktree per session, no container.
- **Deprecated** Feb 2026 in favor of Nimbalyst ([source](https://github.com/stravu/crystal)) — worth noting the trend line.
- **Relevance**: the SQLite + per-panel state model is close to what Ardent Forge should do server-side.

### Claude Squad
- **Architecture**: Go TUI wrapping tmux + git worktree. Supports Claude Code, Codex, Aider, Gemini. `--autoyes` accepts all prompts automatically ([source](https://github.com/smtg-ai/claude-squad)).
- **Relevance**: the terminal-first multi-agent pattern. Ardent Forge replaces the TUI with a web UI but keeps the tmux-less equivalent (per-session subprocess).

### Open Claw / OpenClaude / OpenAgents variants
These are loose designations for a growing pile of Claude-Code wrappers (the user's research list mixes several). Specific relevant ones:

- **opcode / Claudia**: desktop GUI for Claude Code with custom agent creation ([awesome-claude-code.com](https://awesome-claude-code.com/)).
- **Happy**: mobile client for Claude Code with remote access ([awesome-claude-code.com](https://awesome-claude-code.com/)).
- **Dmux, VibeTree, Emdash, Mux**: various parallel-agent orchestration tools; all use worktrees, most don't containerize.

### claude-code-sandbox (textcortex)
- **Architecture**: Docker (or Podman), one container per session, GitHub auto-PR creation, supports browser terminal. Runs `claude --dangerously-skip-permissions` inside the container by design ([source](https://github.com/textcortex/claude-code-sandbox)). **Archived** as of late 2025.

### claudebox (RchGrav)
- **Architecture**: Bash-level Docker wrapper with pre-configured language profiles ([source](https://github.com/RchGrav/claudebox)). Each project gets its own image and is "fully isolated."

### trailofbits/claude-code-devcontainer
- **Architecture**: Devcontainers-CLI driven; builds on Anthropic's reference but hardens it (`chattr +i` on firewall scripts, Colima optimization on Mac). Built specifically for security audit workflows where Claude operates on untrusted code ([source](https://github.com/trailofbits/claude-code-devcontainer)).
- **Relevance**: the *only* wrapper explicitly built against an adversarial-code threat model; good reference for mount/network choices.

### Anthropic's official devcontainer
- Location: `https://github.com/anthropics/claude-code/tree/main/.devcontainer`.
- Contents: `devcontainer.json` + `Dockerfile` + `init-firewall.sh`. The firewall script is the canonical reference for allowlist-based egress control ([documented here](https://code.claude.com/docs/en/devcontainer)).
- The home directory is *not* mounted; commands run as a `node` user; shell history persists via a volume. Useful patterns to steal.

### Warp, Cursor, and IDE-integrated runners
- **Warp**: runs agents directly on the host, no sandbox by default. Its "agent mode" shells out directly.
- **Cursor**: similar — agent tool calls execute on the host with Cursor's permission prompts as the only gate. Recent work has added `--worktree` support for parallel sessions, and a `Cursor CLI` for headless runs.
- **Codex App (OpenAI)**: uses worktrees per task with detached HEAD; runs on the host ([source](https://www.verdent.ai/guides/codex-app-worktrees-explained)).

**Pattern**: The IDE-integrated runners overwhelmingly skip the container boundary because they want IDE integration (file watchers, LSP, diagnostics) that's hard to preserve across a container wall. Ardent Forge explicitly chose not to be IDE-integrated, so this constraint doesn't apply.

### Academic / industry writeups on sandboxing LLM agents
The research literature on this specific topic is thin as of April 2026. The closest adjacent work:

- **"The True Cost of Containing: A gVisor Case Study"** (USENIX HotCloud'19) — foundational measurements of syscall-interception overhead, relevant when sizing the microVM-vs-container tradeoff ([source](https://www.usenix.org/system/files/hotcloud19-paper-young.pdf)).
- **OpenTelemetry GenAI Semantic Conventions** v1.37 — industry convergence on how to trace LLM/agent workloads ([source](https://www.datadoghq.com/blog/llm-otel-semantic-convention/)).
- **Docker's own writeup on microVM isolation for agents** — not peer-reviewed but useful industry framing ([source](https://www.docker.com/blog/docker-sandboxes-run-claude-code-and-other-coding-agents-unsupervised-but-safely/)).

For agent-specific security threat-modeling (prompt injection leading to tool-call abuse, etc.), the published state of the art is mostly OWASP LLM Top 10 and Anthropic's own responsible-deployment posts; nothing that changes the architectural choices here.

---

## 7. User-Stack-Specific Guidance

### 7.1 NixOS + Podman + Systemd + Quadlet

The correct approach in 2026:

- `virtualisation.podman.enable = true;` and `virtualisation.quadlet.enable = true;` (via the [`quadlet-nix`](https://github.com/SEIAROTg/quadlet-nix) flake).
- User-level quadlet units (via home-manager) for rootless containers. `users.users.<name>.linger = true;` + `autoSubUidGidRange = true;`.
- The older `virtualisation.oci-containers` module is "limited options, lack of support for networks, pods, etc." and works on Docker and Podman but is not the path forward ([source](https://github.com/SEIAROTg/quadlet-nix)). Quadlet is the modern systemd-native approach ([Red Hat](https://www.redhat.com/en/blog/quadlet-podman)) and `quadlet-nix` exposes it as typed Nix options.
- One `.container` unit for Ardent Forge itself; one `.container` unit per project (generated from project metadata declaratively).

Example sketch (pseudo-nix):

```nix
virtualisation.quadlet.containers.ardent-forge = {
  autoStart = true;
  containerConfig = {
    image = "ardent-forge:latest";
    publishPorts = [ "127.0.0.1:8080:8080" ];  # tailscale'd reverse proxy in front
    volumes = [
      "/home/you/.local/share/ardent-forge:/state"
      "%t/podman/podman.sock:/run/podman/podman.sock"  # see 7.2
    ];
  };
};
```

### 7.2 Exposing Podman to Ardent Forge

Three options:

1. **Podman REST API socket** (recommended): `systemctl --user enable --now podman.socket` exposes the Docker-compatible and libpod APIs at `$XDG_RUNTIME_DIR/podman/podman.sock` on demand via socket activation ([docs](https://github.com/containers/podman/blob/main/docs/tutorials/socket_activation.md)). Ardent Forge talks to this via HTTP-over-Unix. The `bollard` Rust crate works (Docker-compat endpoint); there's also a `podman-autogen-api` Rust crate for the libpod-native endpoint.
2. **`podman` CLI via `Command::spawn`**: simplest, least efficient. Fine for low-frequency ops (container create/start/stop).
3. **Direct `podman exec` subprocess for session invocation**: always use this path for the agent subprocess itself, because you want to own the stdout stream directly.

**Security note from Podman's own docs**: "the API grants full access to all Podman functionality, and thus allows arbitrary code execution as the user running the API, with no ability to limit or audit this access" ([source](https://docs.podman.io/en/latest/markdown/podman-system-service.1.html)). So: (a) keep the socket rootless-user-owned, (b) never bind-mount it into an agent's container, (c) if Ardent Forge runs *in a container*, mount only Ardent Forge's own socket into Ardent Forge's container, never into agent containers.

### 7.3 OpenTelemetry for Agent Sessions

Use OpenTelemetry GenAI Semantic Conventions (v1.37+) where they fit. Per [the OTel blog post on AI agent observability](https://opentelemetry.io/blog/2025/ai-agent-observability/) and [Uptrace's writeup](https://uptrace.dev/blog/opentelemetry-ai-systems):

**Per-session span tree**:

- Root span: `ardent_forge.session` (attrs: `session.id`, `project.id`, `agent.type=claude-code`, `git.branch`, `worktree.path`).
- Child: `gen_ai.chat` per LLM turn (attrs: `gen_ai.system=anthropic`, `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`).
- Child of that: `gen_ai.tool.call` per tool invocation (attrs: `gen_ai.tool.name`, `gen_ai.tool.call.id`, duration).
- Prompts and completions: **as span events, not attributes**, capped to 500-1000 chars and behind a toggle for privacy ([source](https://uptrace.dev/blog/opentelemetry-ai-systems)).

**Stack**:

- Agent sessions in Ardent Forge → OTel SDK (Rust `opentelemetry` + `opentelemetry-otlp`) → local OTel Collector → Tempo (or directly to a local Jaeger if you already run it) + Prometheus (for metric aggregation) + Loki (for log stream).
- Correlate UI sessions with container-level traces by propagating `trace_id` from the HTTP request (SSE or WS origination) through to the `podman exec` subprocess as an env var (`TRACEPARENT`).
- The LangSmith/Langfuse ecosystem is worth knowing about for richer agent-specific viewers, but for a homelab, the Grafana/Tempo stack is enough.

Metrics worth emitting:

- `ardent_forge.session.active` (gauge per state).
- `ardent_forge.session.duration_seconds` (histogram).
- `gen_ai.usage.tokens` (counter, labeled by model).
- `ardent_forge.container.count` (gauge per project).
- `ardent_forge.container.mem_bytes`, `..._cpu_seconds_total` (from `podman stats --format json` scraped periodically).

### 7.4 Integration with Linear, GitHub, jj

- **Linear**: Linear has a well-documented REST/GraphQL API; a lightweight integration lets Ardent Forge create issues from agent output (`/forge linear "fix X"`) and attach sessions to existing issues. Authenticate with a personal API key stored in agenix; expose it to Ardent Forge itself (not to agent containers).
- **GitHub PR creation**: the agent should create PRs via `gh pr create` using a **fine-grained PAT scoped to the specific repo**, not your personal full-scope token. Generate one PAT per project, store in agenix, inject as `GH_TOKEN` env var at container start. This is the only credential that should ever touch an agent container.
- **Jujutsu (jj)**: jj's design plays well with worktrees — in fact, jj's native workspace model is analogous to git worktrees. If the user wants to use jj as the VCS inside containers, the main caveat is that jj's colocated-git mode is still the safer path for interop with tools that expect git (and most agent tools do). The git-worktree pattern this document recommends works unchanged under jj-colocated-git.

---

## 8. Recommended Concrete Architecture

Below is a specific, implementable design synthesizing the research.

### 8.1 System Layout

```
NixOS host (Bee Link mini PC)
├─ rootless user "you" with linger=true, autoSubUidGidRange=true
├─ Quadlet units (user scope, via quadlet-nix + home-manager):
│  ├─ ardent-forge.container    → web UI + control plane (Rust + Svelte 5)
│  ├─ project-<slug>.container  → one per project, long-lived
│  ├─ loki.container, prometheus.container, grafana.container, tempo.container
│  └─ otel-collector.container
├─ Host services (NixOS modules):
│  ├─ tailscale (tailnet access only)
│  ├─ nftables (egress allowlist, per-container)
│  └─ blocky (DNS, with allowlist mode)
└─ agenix secrets (decrypted only on host, never bind-mounted into agent containers)
```

### 8.2 Project Container Template

```nix
# Generated per-project by Ardent Forge from project config
virtualisation.quadlet.containers.project-foo = {
  autoStart = true;
  containerConfig = {
    image = "ardent-forge/devbase:latest";  # or project-specific image
    userns = "keep-id:uid=1000,gid=1000";
    # Same path inside and outside the container
    volumes = [
      "/home/you/code/foo:/home/you/code/foo"
      # Shared caches (across all project containers)
      "cache-cargo:/home/you/.cargo/registry"
      "cache-cargo-target:/home/you/.cache/cargo-target"
      "cache-pnpm:/home/you/.local/share/pnpm"
      "cache-go:/home/you/go/pkg/mod"
      # Agent state (per-project)
      "claude-state-foo:/home/you/.claude"
    ];
    # Explicit capability drop
    dropCapabilities = [ "ALL" ];
    # No new privs
    noNewPrivileges = true;
    # Default seccomp
    # (nothing to specify; Podman's default applies)
    # Network — custom bridge, nftables on host applies allowlist
    network = [ "ardent-egress-restricted" ];
    # DNS to local Blocky
    dns = [ "127.0.0.1" ];
    # Environment
    environmentFile = [ "/run/agenix/anthropic-api-key" ];
    # Long-lived; no exec by default
    exec = "sleep infinity";
  };
};
```

### 8.3 Agent Invocation

Ardent Forge, on "start new session":

1. `git worktree add ~/code/foo/.worktrees/sess-abc -b forge/sess-abc main` (inside the container via `podman exec`).
2. `podman exec -d project-foo setsid bash -c "cd ~/code/foo/.worktrees/sess-abc && exec claude -p '$PROMPT' --output-format stream-json --include-partial-messages --verbose --dangerously-skip-permissions --resume ''"`.
3. Capture the PID, parse NDJSON from stdout via an async Rust subprocess reader, tee to `sessions/<id>.jsonl`, broadcast parsed events over SSE.
4. Update SQLite session state; emit OTel spans.

### 8.4 Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Host OS | NixOS | User requirement |
| Container runtime | Rootless Podman + Quadlet | Daemonless, systemd-native, declarative via Nix |
| Container definitions | `quadlet-nix` | Typed, declarative, current best-in-class |
| Ardent Forge backend | Rust (axum + tokio + sqlx + rusqlite) | User's stack; async subprocess handling is the core workload |
| Podman client | `bollard` or direct subprocess | Simplicity wins; use subprocess where it does |
| Persistence | SQLite (WAL) + JSONL files on disk | Single-user scale |
| Streaming | SSE for events, WebSocket for terminal PTY | Right shape for each |
| Frontend | Svelte 5 + SvelteKit (SPA mode) | User preference |
| Terminal | xterm.js + attach addon | Standard |
| Diff viewer | Monaco's diff editor | Standard |
| Auth | None in-app; Tailscale ACLs | Single-user; simplest secure default |
| Observability | OTel → Collector → Tempo/Prometheus/Loki → Grafana | User already plans this |
| Secrets | agenix on host, only injected at container start as env vars | Never bind-mount decrypted secrets |
| Network egress | Host nftables allowlist per container + Blocky DNS allowlist | Defense in depth without container capabilities |

### 8.5 Milestones

1. **M1 (week 1-2)**: Rootless Podman + Quadlet-nix working for a single long-lived dev container. `podman exec` Claude works interactively. Verify keep-id file ownership, verify shared cargo cache works.
2. **M2 (week 2-3)**: Ardent Forge v0: Rust service, SQLite, single project, single session, SSE streaming of `stream-json`, minimal Svelte UI listing sessions + one transcript view.
3. **M3 (week 3-4)**: Multi-session with worktree-per-session, session state machine, kill/resume, basic tool-call-specific UI components.
4. **M4**: nftables egress allowlist, audit what domains Claude actually contacts in a real session, lock down. GitHub PAT injection for `gh pr create`.
5. **M5**: OTel instrumentation, Grafana dashboards. Linear integration.
6. **M6**: intervention features (inject message, approve gated tool call via hooks), notifications.
7. **M7 (only if needed)**: container rebuild automation, image versioning, multi-project UX polish.

### 8.6 Things That Sound Right But Are Traps

- **"Let's use `--userns=auto` for better isolation between containers."** Breaks shared caches, breaks bind mounts with predictable ownership, breaks `keep-id`'s whole point. Only worth it in multi-tenant settings.
- **"Let's give the container `NET_ADMIN` and run iptables inside to enforce the firewall like Anthropic's devcontainer."** Requires giving the container significant privilege; fragile across container restarts. Host nftables is strictly better for a Linux homelab.
- **"Let's bind-mount `~/.config/gh` so the agent can `gh pr create`."** This is the single most common mistake in agent-container setups. Your full-scope GitHub token becomes exfiltration-accessible. Use repo-scoped PATs instead.
- **"Let's bind-mount the Docker/Podman socket so the agent can run containers."** Same class of error — trivial container escape. If the agent genuinely needs this, use Sysbox or a separate, more isolated sub-runtime.
- **"Let's use Postgres from the start for session state, we might need it later."** You won't. SQLite with WAL handles everything at your scale and is materially less operational work.
- **"Let's persist containers between host reboots via `podman checkpoint`."** Podman's CRIU-based checkpoint/restore works but is brittle enough that for dev containers you're better off just `podman start`-ing them fresh. Containers should be cheap to recreate.
- **"Let's give each session its own container like Sculptor."** Materially more resource use on a Bee Link. Worktrees-in-one-container is sufficient for a single user. You can always escalate later.
- **"OAuth through Claude Max token in the container, mount `~/.claude`."** Mounts your entire Claude credential store into a sandbox running agent code. The sandbox is for the agent, not trusted with your auth. Use an API key from agenix injected as env var at container start, and keep `.claude` as a named Podman volume inside the container.
- **"Let's run Claude Code *without* `--dangerously-skip-permissions` as a safety net."** In a full container sandbox with no host secret access and an egress allowlist, the permission prompts just add friction. The user's stated design (container == sandbox, skip permissions) is the correct tradeoff *given* the other defenses are in place. It's wrong to skip permissions *and* skip the sandbox.
- **"Let's use VS Code devcontainers to run the agent."** VS Code injects IPC sockets and environment variables into the container. If Ardent Forge is the UI, drive the container directly via `podman exec` — no VS Code in the loop.
- **"Let's use Docker Desktop on NixOS for compatibility."** Docker Desktop on Linux runs Docker inside a VM. You lose the performance and integration advantages of native rootless containers. Use Podman directly.
- **"Let's expose Ardent Forge on 0.0.0.0 behind Authelia."** Adds a non-trivial auth stack to manage. Tailscale-only binding eliminates an entire class of problem.

---

## 9. Key Sources

- [Claude Code devcontainer docs](https://code.claude.com/docs/en/devcontainer)
- [Claude Code sandboxing docs](https://code.claude.com/docs/en/sandboxing)
- [Claude Agent SDK streaming output](https://platform.claude.com/docs/en/agent-sdk/streaming-output)
- [Sculptor container architecture](https://docs.imbue.com/features/containers) and [launch post](https://imbue.com/sculptor-announce/)
- [Sculptor dev containers for faster startup](https://imbue.com/product/containers/)
- [container-use by Dagger](https://github.com/dagger/container-use) and [blog](https://dagger.io/blog/agent-container-use/)
- [Conductor architecture interview](https://elite-ai-assisted-coding.dev/p/the-parallel-agent-multiplier-conductor-with-charlie-holtz)
- [Crystal architecture](https://deepwiki.com/stravu/crystal) and [CLAUDE.md](https://github.com/stravu/crystal/blob/main/CLAUDE.md)
- [Claude Squad](https://github.com/smtg-ai/claude-squad)
- [Trail of Bits claude-code-devcontainer](https://github.com/trailofbits/claude-code-devcontainer)
- [Docker Sandboxes for coding agents](https://www.docker.com/blog/docker-sandboxes-run-claude-code-and-other-coding-agents-unsupervised-but-safely/)
- [E2B architecture breakdown](https://memo.d.foundation/breakdown/e2b)
- [gVisor performance guide](https://gvisor.dev/docs/architecture_guide/performance/) and [HotCloud'19 paper](https://www.usenix.org/system/files/hotcloud19-paper-young.pdf)
- [Podman rootless userns modes](https://www.redhat.com/en/blog/rootless-podman-user-namespace-modes)
- [Podman rootless tutorial](https://github.com/containers/podman/blob/main/docs/tutorials/rootless_tutorial.md)
- [Rootless Podman security posture](https://blog.nviso.eu/2026/02/03/rootless-containers-with-podman/)
- [Podman vs rootful userns tradeoff](https://github.com/containers/podman/discussions/13728)
- [Podman system service / REST API](https://docs.podman.io/en/latest/markdown/podman-system-service.1.html)
- [Podman socket activation](https://github.com/containers/podman/blob/main/docs/tutorials/socket_activation.md)
- [Quadlet on NixOS via quadlet-nix](https://github.com/SEIAROTg/quadlet-nix)
- [Quadlet overview (Red Hat)](https://www.redhat.com/en/blog/quadlet-podman)
- [NixOS container docs](https://wiki.nixos.org/wiki/Docker)
- [nix2container](https://github.com/nlewo/nix2container)
- [Flox on Nix + containers](https://flox.dev/blog/nix-and-containers-why-not-both/)
- [Git worktrees for parallel AI agents (multiple refs)](https://www.augmentcode.com/guides/git-worktrees-parallel-ai-agent-execution), [Upsun](https://devcenter.upsun.com/posts/git-worktrees-for-parallel-ai-coding-agents/), [Termdock troubleshooting](https://www.termdock.com/en/blog/git-worktree-conflicts-ai-agents)
- [Anthropic's bash_command_validator_example pattern](https://mitjamartini.com/posts/claude-code-in-devcontainer/)
- [stream-json format](https://theouterloop.substack.com/p/a-few-fun-things-you-can-do-with) and [stream-json as background-agent engine](https://backgroundclaude.com/blog/stream-json)
- [xterm.js reference integrations](https://xtermjs.org/) and [React integration example](https://www.qovery.com/blog/react-xtermjs-a-react-library-to-build-terminals)
- [Tailscale for self-hosting](https://selfhosting.sh/foundations/tailscale-setup/) and [Headscale alternative](https://github.com/juanfont/headscale)
- [OpenTelemetry GenAI Semantic Conventions](https://www.datadoghq.com/blog/llm-otel-semantic-convention/) and [Uptrace guide](https://uptrace.dev/blog/opentelemetry-ai-systems)
- [OTel AI agent observability](https://opentelemetry.io/blog/2025/ai-agent-observability/)
- [Podman seccomp custom profiles](https://docs.podman.io/en/v4.6.0/markdown/options/security-opt.html) and [generating with eBPF](https://podman.io/blogs/2019/10/15/generate-seccomp-profiles.html)

---

## 10. Bottom Line

For a senior engineer building for themselves on a NixOS Bee Link homelab, the stated design is largely correct and the research strongly supports it with a few sharpenings:

- **Keep the one-long-lived-container-per-project design**, but add **git worktrees inside** for parallelism rather than escalating to container-per-session.
- **Commit hard to rootless Podman + Quadlet-nix + `keep-id` userns.** It's the setup that actually makes same-path bind mounts and clean file ownership work without ceremony.
- **The highest-leverage security investment is not seccomp/SELinux/caps — it's the host-level nftables egress allowlist plus *never* bind-mounting secrets.** Anthropic's own reference makes this same point.
- **Tailscale + no app auth** is genuinely the right answer for a solo operator.
- **Rust control plane + SQLite + JSONL transcripts + SSE + Svelte 5** is boring, right-sized, and lets the interesting work happen in the agent-session domain rather than the infrastructure domain.
- **Resist the urge to copy Sculptor's container-per-agent model.** It solves a problem you don't have (package-install races across simultaneous agents) at a cost you shouldn't pay (N containers per project). Worktrees in one container is enough.
- **Build `forge rebuild <project>` early.** The long-lived container is a pet-or-cattle choice; you want cattle, and the only way to keep it honest is to make teardown-and-recreate a one-command operation.

That's Ardent Forge.
