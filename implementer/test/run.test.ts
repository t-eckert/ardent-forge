import { existsSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { LockHeldError, ProcessLock } from "../src/lock.ts";
import { processPaths } from "../src/processes.ts";
import { runProcess } from "../src/run.ts";

function deferred() {
	let resolve!: () => void;
	const promise = new Promise<void>((r) => {
		resolve = r;
	});
	return { promise, resolve };
}

/** Port 0 everywhere: each listener takes any free port. */
const PORTS = { gateway: 0, implementer: 0 };

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

describe("runProcess", () => {
	it("opens its database, holds the lock while running, and exits 0 on shutdown", async () => {
		const stateDir = mkdtempSync(join(tmpdir(), "implementer-run-"));
		const paths = processPaths(stateDir, "implementer");
		const shutdown = deferred();
		const logs: string[] = [];

		const exit = runProcess({
			name: "implementer",
			stateDir,
			graceMs: 1000,
			closeDeadlineMs: 5000,
			shutdown: shutdown.promise,
			log: (m) => logs.push(m),
			ports: PORTS,
			linearSecrets: {},
		});
		await wait(500);

		expect(existsSync(paths.database)).toBe(true);
		expect(() => ProcessLock.acquire(paths.lock)).toThrow(LockHeldError);

		shutdown.resolve();
		expect(await exit).toBe(0);
		expect(logs).toContain("implementer: closed cleanly");
		ProcessLock.acquire(paths.lock).release();
	});

	it("runs the gateway without a harness", async () => {
		const stateDir = mkdtempSync(join(tmpdir(), "implementer-run-"));
		const shutdown = deferred();
		const exit = runProcess({
			name: "gateway",
			stateDir,
			graceMs: 1000,
			closeDeadlineMs: 5000,
			shutdown: shutdown.promise,
			log: () => {},
			ports: PORTS,
			linearSecrets: {},
		});
		await wait(100);
		shutdown.resolve();
		expect(await exit).toBe(0);
		expect(existsSync(processPaths(stateDir, "gateway").database)).toBe(false);
	});
});
