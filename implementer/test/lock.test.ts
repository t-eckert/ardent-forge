import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { LockHeldError, ProcessLock } from "../src/lock.ts";

describe("ProcessLock", () => {
	const path = () => join(mkdtempSync(join(tmpdir(), "implementer-lock-")), "test.lock");

	it("refuses a second holder while the first holds the lock", () => {
		const file = path();
		const first = ProcessLock.acquire(file);
		expect(() => ProcessLock.acquire(file)).toThrow(LockHeldError);
		first.release();
	});

	it("can be taken again once released", () => {
		const file = path();
		ProcessLock.acquire(file).release();
		const again = ProcessLock.acquire(file);
		again.release();
	});

	it("releasing twice is harmless", () => {
		const lock = ProcessLock.acquire(path());
		lock.release();
		lock.release();
	});
});
