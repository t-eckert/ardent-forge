import { existsSync, mkdtempSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { describe, expect, it } from "vitest";
import { snapshotLocal } from "../src/snapshot.ts";

function scratch() {
	const dir = mkdtempSync(join(tmpdir(), "implementer-snapshot-"));
	return { database: join(dir, "p.sqlite"), snapshots: join(dir, "snapshots") };
}

describe("snapshotLocal", () => {
	it("skips a process that has no database yet", () => {
		const paths = scratch();
		const result = snapshotLocal({ ...paths, keep: 5 });
		expect(result.kind).toBe("skipped");
		expect(existsSync(paths.snapshots)).toBe(false);
	});

	it("captures commits still in the WAL of a database another connection holds open", () => {
		const paths = scratch();
		const live = new DatabaseSync(paths.database);
		live.exec("PRAGMA journal_mode = WAL; PRAGMA wal_autocheckpoint = 0;");
		live.exec("CREATE TABLE t (v TEXT); INSERT INTO t VALUES ('in the wal');");

		const result = snapshotLocal({ ...paths, keep: 5 });
		live.close();

		expect(result.kind).toBe("written");
		if (result.kind !== "written") return;
		const copy = new DatabaseSync(result.path, { readOnly: true });
		expect(copy.prepare("SELECT v FROM t").get()).toEqual({ v: "in the wal" });
		copy.close();
	});

	it("keeps only the newest snapshots", () => {
		const paths = scratch();
		const db = new DatabaseSync(paths.database);
		db.exec("CREATE TABLE t (v INTEGER)");
		db.close();

		for (let i = 0; i < 4; i++) {
			snapshotLocal({ ...paths, keep: 2, now: new Date(Date.UTC(2026, 9, 29, 12, 0, i)) });
		}
		expect(readdirSync(paths.snapshots).sort()).toEqual([
			"2026-10-29T12-00-02-000Z.sqlite",
			"2026-10-29T12-00-03-000Z.sqlite",
		]);
	});
});
