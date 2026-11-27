import { join } from "node:path";

/** The two processes: the gateway, which receives webhooks, and the implementer, which runs tickets. */
export const PROCESSES = ["gateway", "implementer"] as const;
export type ProcessName = (typeof PROCESSES)[number];

/** The gateway keeps only a spool of undelivered events, never a Pi Durable harness. */
export function hasHarness(name: ProcessName): boolean {
	return name !== "gateway";
}

export function parseProcessName(value: string | undefined): ProcessName {
	if (value !== undefined && (PROCESSES as readonly string[]).includes(value)) {
		return value as ProcessName;
	}
	throw new UsageError(`expected a process name, one of: ${PROCESSES.join(", ")}; got ${value ?? "nothing"}`);
}

/**
 * Each process's port on localhost. The gateway's is the one `cloudflared` routes to; the others take the gateway's
 * hand-off. Overridden with `IMPLEMENTER_<PROCESS>_PORT`.
 */
export const DEFAULT_PORTS: Readonly<Record<ProcessName, number>> = {
	gateway: 7410,
	implementer: 7411,
};

/** Where one process keeps its state: `<stateDir>/<process>/`. */
export function processPaths(stateDir: string, name: ProcessName) {
	const dir = join(stateDir, name);
	return {
		dir,
		database: join(dir, `${name}.sqlite`),
		lock: join(dir, `${name}.lock`),
		snapshots: join(dir, "snapshots"),
		spool: join(dir, "spool.jsonl"),
	};
}

export class UsageError extends Error {}
