import { DatabaseSync } from "node:sqlite";

/**
 * An exclusive lock on `<process>.lock` for as long as `implementer run` holds it.
 *
 * Pi Durable does no locking between processes, so implementer keeps its own. The lock is SQLite's: an exclusive
 * transaction on a small database file, which SQLite holds with an fcntl lock. The operating system releases that
 * lock when the process dies, so a crash never leaves a stale lock behind, which a pid file cannot promise.
 */
export class ProcessLock {
	private constructor(private readonly db: DatabaseSync) {}

	/** Takes the lock, or throws `LockHeldError` at once if another holder has it. Never waits. */
	static acquire(path: string): ProcessLock {
		const db = new DatabaseSync(path);
		try {
			db.exec("PRAGMA busy_timeout = 0; PRAGMA locking_mode = EXCLUSIVE; BEGIN EXCLUSIVE;");
		} catch (error) {
			db.close();
			if (isBusy(error)) {
				throw new LockHeldError(path);
			}
			throw error;
		}
		return new ProcessLock(db);
	}

	release(): void {
		if (this.db.isOpen) {
			this.db.close();
		}
	}
}

export class LockHeldError extends Error {
	constructor(readonly path: string) {
		super(`another implementer process holds ${path}`);
	}
}

function isBusy(error: unknown): boolean {
	return error instanceof Error && /database is locked|SQLITE_BUSY/i.test(error.message);
}
