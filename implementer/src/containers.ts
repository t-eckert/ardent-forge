import { spawn } from "node:child_process";
import { createWriteStream, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import type { ProcessName } from "./processes.ts";

/** One container run: a Claude Code session, a check, or the fence probe. */
export type ContainerSpec = {
	/** Names and labels the container, so it can be stopped, and found again after a crash. */
	readonly runId: string;
	readonly image: string;
	/** The worktree, mounted at `/work`. The only part of the host the container sees, apart from the cache. */
	readonly worktree: string;
	readonly command: readonly string[];
	readonly env?: Readonly<Record<string, string>>;
	/** Where the combined stdout and stderr go. Transcripts stay out of SQLite. */
	readonly outputPath: string;
};

export type ContainerResult = {
	/** The command's exit code, or undefined when it was stopped by an abort. */
	readonly exitCode: number | undefined;
	/** The end of the output: compilers put the useful part last, so it is truncated from the start. */
	readonly tail: string;
};

export type ContainersOptions = {
	readonly process: ProcessName;
	/** Shared across sessions, so builds reuse each other's work. Mounted at `/cache`. */
	readonly cacheDir: string;
	/** The crucible proxy, such as `http://127.0.0.1:3128`. Without one, the container has no proxy variables. */
	readonly proxy?: string | undefined;
	readonly podman?: string;
	/**
	 * Podman's `--cgroups` mode. `split` keeps the container's processes in the unit's own cgroup, so the slice's
	 * egress floor and memory limit apply to them. It needs a unit with `Delegate=yes`; tests outside one use `enabled`.
	 */
	readonly cgroups?: "split" | "enabled";
	readonly log: (message: string) => void;
};

/** How long `podman stop` waits after SIGTERM before it kills the container. */
const STOP_TIMEOUT_SECONDS = 10;
const TAIL_BYTES = 16 * 1024;
const LABEL_PROCESS = "implementer.process";
const LABEL_RUN = "implementer.run-id";

/**
 * Runs the implementer's containers with rootless Podman, one at a time. See docs/design.md, "Isolating a session".
 *
 * Each container shares the host's network namespace, so it can reach the crucible proxy on the host's loopback, and
 * goes out only through it. It holds the worktree and the shared cache, nothing else from the host, runs as the
 * implementer's own uid, and has no capabilities.
 */
export class Containers {
	private queue: Promise<unknown> = Promise.resolve();

	constructor(private readonly options: ContainersOptions) {}

	/**
	 * Runs `spec` to completion, after any run already in progress. When `signal` aborts, the container is stopped and
	 * the result has no exit code.
	 */
	run(spec: ContainerSpec, signal?: AbortSignal): Promise<ContainerResult> {
		const turn = this.queue.then(() => this.runNow(spec, signal));
		this.queue = turn.catch(() => {});
		return turn;
	}

	/** The `podman run` arguments for `spec`. Exposed for tests. */
	args(spec: ContainerSpec): string[] {
		const cache = this.options.cacheDir;
		const env: Record<string, string> = {
			HOME: "/cache/home",
			CARGO_HOME: "/cache/cargo",
			CARGO_TARGET_DIR: "/cache/target",
			npm_config_cache: "/cache/npm",
			PNPM_HOME: "/cache/pnpm",
			npm_config_store_dir: "/cache/pnpm-store",
			...proxyEnv(this.options.proxy),
			...spec.env,
		};
		return [
			"run",
			"--rm",
			"--name",
			containerName(spec.runId),
			"--label",
			`${LABEL_PROCESS}=${this.options.process}`,
			"--label",
			`${LABEL_RUN}=${spec.runId}`,
			"--network=host",
			`--cgroups=${this.options.cgroups ?? "split"}`,
			"--userns=keep-id",
			"--cap-drop=all",
			"--security-opt=no-new-privileges",
			"--pids-limit=4096",
			"--volume",
			`${spec.worktree}:/work`,
			"--volume",
			`${cache}:/cache`,
			"--workdir",
			"/work",
			...Object.entries(env).flatMap(([k, v]) => ["--env", `${k}=${v}`]),
			spec.image,
			...spec.command,
		];
	}

	/** Stops the container for `runId`, if there is one. */
	async stop(runId: string): Promise<void> {
		await this.podman(["stop", "--ignore", "--time", String(STOP_TIMEOUT_SECONDS), containerName(runId)]);
	}

	/**
	 * Removes every container this process started, and returns their names.
	 *
	 * Called when the process starts, before it resumes any task. Nothing is running yet, so every labelled container
	 * was left by an earlier process that crashed. A run that was cut off starts a fresh container on the same worktree
	 * when it resumes.
	 */
	async reap(): Promise<string[]> {
		const listed = await this.podman([
			"ps",
			"--all",
			"--filter",
			`label=${LABEL_PROCESS}=${this.options.process}`,
			"--format",
			"{{.Names}}",
		]);
		const names = listed.stdout.split("\n").filter((n) => n !== "");
		if (names.length > 0) {
			await this.podman(["rm", "--force", "--time", String(STOP_TIMEOUT_SECONDS), ...names]);
			this.options.log(`${this.options.process}: removed containers left by an earlier run: ${names.join(", ")}`);
		}
		return names;
	}

	private async runNow(spec: ContainerSpec, signal: AbortSignal | undefined): Promise<ContainerResult> {
		if (signal?.aborted) {
			return { exitCode: undefined, tail: "" };
		}
		mkdirSync(dirname(spec.outputPath), { recursive: true });
		for (const sub of ["home", "cargo", "target", "npm", "pnpm", "pnpm-store"]) {
			mkdirSync(join(this.options.cacheDir, sub), { recursive: true });
		}

		const output = createWriteStream(spec.outputPath, { flags: "a" });
		let tail = Buffer.alloc(0);
		const child = spawn(this.options.podman ?? "podman", this.args(spec), { stdio: ["ignore", "pipe", "pipe"] });
		const keep = (chunk: Buffer) => {
			output.write(chunk);
			tail = Buffer.concat([tail, chunk]);
			if (tail.length > TAIL_BYTES) {
				tail = tail.subarray(tail.length - TAIL_BYTES);
			}
		};
		child.stdout.on("data", keep);
		child.stderr.on("data", keep);

		let aborted = false;
		const onAbort = () => {
			aborted = true;
			this.options.log(`${this.options.process}: stopping container for ${spec.runId}`);
			this.stop(spec.runId).catch((error: unknown) =>
				this.options.log(`${this.options.process}: could not stop ${spec.runId}: ${String(error)}`),
			);
		};
		signal?.addEventListener("abort", onAbort, { once: true });

		try {
			const exitCode = await new Promise<number | null>((resolve, reject) => {
				child.once("error", reject);
				child.once("close", (code) => resolve(code));
			});
			return { exitCode: aborted ? undefined : (exitCode ?? undefined), tail: tail.toString("utf8") };
		} finally {
			signal?.removeEventListener("abort", onAbort);
			await new Promise<void>((resolve) => output.end(() => resolve()));
		}
	}

	private podman(args: readonly string[]): Promise<{ stdout: string }> {
		return new Promise((resolve, reject) => {
			const child = spawn(this.options.podman ?? "podman", args, { stdio: ["ignore", "pipe", "pipe"] });
			let stdout = "";
			let stderr = "";
			child.stdout.on("data", (chunk: Buffer) => {
				stdout += chunk.toString("utf8");
			});
			child.stderr.on("data", (chunk: Buffer) => {
				stderr += chunk.toString("utf8");
			});
			child.once("error", reject);
			child.once("close", (code) => {
				if (code === 0) {
					resolve({ stdout });
				} else {
					reject(new Error(`podman ${args[0]} exited ${code}: ${stderr.trim()}`));
				}
			});
		});
	}
}

export function containerName(runId: string): string {
	return `implementer-${runId.replace(/[^A-Za-z0-9_.-]/g, "-")}`;
}

function proxyEnv(proxy: string | undefined): Record<string, string> {
	if (proxy === undefined) {
		return {};
	}
	// Both spellings: curl reads the lower-case ones, most other tools the upper-case.
	return {
		HTTP_PROXY: proxy,
		HTTPS_PROXY: proxy,
		http_proxy: proxy,
		https_proxy: proxy,
		NO_PROXY: "localhost,127.0.0.1,::1",
		no_proxy: "localhost,127.0.0.1,::1",
	};
}
