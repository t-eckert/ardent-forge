import { existsSync, mkdirSync, readdirSync, rmSync } from "node:fs";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";

export type SnapshotResult =
	| { readonly kind: "skipped"; readonly reason: string }
	| { readonly kind: "written"; readonly path: string; readonly pruned: readonly string[] };

/**
 * `implementer backup --local`: a consistent snapshot of one process's database, kept on disk beside it.
 *
 * Runs before the process starts, so a Pi Durable upgrade that migrates the schema with no way back can still be
 * rolled back. `VACUUM INTO` writes a consistent copy from a live connection, so it is safe even if the database is
 * in WAL mode with commits still in the side file. A plain file copy is not. Uploads nothing and holds no storage key.
 */
export function snapshotLocal(options: {
	readonly database: string;
	readonly snapshots: string;
	readonly keep: number;
	readonly now?: Date;
}): SnapshotResult {
	if (!existsSync(options.database)) {
		return { kind: "skipped", reason: `no database at ${options.database} yet` };
	}
	mkdirSync(options.snapshots, { recursive: true });

	const stamp = (options.now ?? new Date()).toISOString().replace(/[:.]/g, "-");
	const path = join(options.snapshots, `${stamp}.sqlite`);

	const source = new DatabaseSync(options.database);
	try {
		source.prepare("VACUUM INTO ?").run(path);
	} finally {
		source.close();
	}

	const check = new DatabaseSync(path, { readOnly: true });
	let verdict: string;
	try {
		const row = check.prepare("PRAGMA integrity_check").get() as { integrity_check: string } | undefined;
		verdict = row?.integrity_check ?? "no result";
	} finally {
		check.close();
	}
	if (verdict !== "ok") {
		rmSync(path, { force: true });
		throw new Error(`snapshot of ${options.database} failed its integrity check: ${verdict}`);
	}

	return { kind: "written", path, pruned: prune(options.snapshots, options.keep) };
}

/** Keeps the newest `keep` snapshots and removes the rest. Names sort by time, because they start with it. */
function prune(dir: string, keep: number): string[] {
	const snapshots = readdirSync(dir)
		.filter((name) => name.endsWith(".sqlite"))
		.sort();
	const doomed = snapshots.slice(0, Math.max(0, snapshots.length - keep));
	for (const name of doomed) {
		rmSync(join(dir, name), { force: true });
	}
	return doomed.map((name) => join(dir, name));
}
