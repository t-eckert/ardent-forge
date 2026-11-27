import { appendFileSync, mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { Spool, type SpooledEvent } from "../src/spool.ts";

function scratch() {
	return join(mkdtempSync(join(tmpdir(), "implementer-spool-")), "spool.jsonl");
}

function event(id: string, target: SpooledEvent["target"] = "implementer"): SpooledEvent {
	return { id, target, source: "linear", receivedAt: 1, signature: "sig", body: Buffer.from(id).toString("base64") };
}

describe("Spool", () => {
	it("keeps pending events across a reopen and forgets accepted ones", () => {
		const path = scratch();
		const spool = Spool.open(path);
		spool.add(event("a"));
		spool.add(event("b"));
		spool.add(event("c"));
		spool.done("b");
		spool.rejected("c", 401);
		spool.close();

		const reopened = Spool.open(path);
		expect(reopened.list().map((e) => e.id)).toEqual(["a"]);
		reopened.close();
	});

	it("hands out each target's events oldest first", () => {
		const spool = Spool.open(scratch());
		spool.add(event("a", "gateway"));
		spool.add(event("b", "implementer"));
		spool.add(event("c", "implementer"));
		expect(spool.next("implementer")?.id).toBe("b");
		spool.done("b");
		expect(spool.next("implementer")?.id).toBe("c");
		expect(spool.next("gateway")?.id).toBe("a");
		spool.done("a");
		expect(spool.next("gateway")).toBeUndefined();
		spool.close();
	});

	it("does not add an id that is already pending", () => {
		const spool = Spool.open(scratch());
		expect(spool.add(event("a"))).toBe(true);
		expect(spool.add(event("a"))).toBe(false);
		expect(spool.list()).toHaveLength(1);
		spool.close();
	});

	it("drops a torn last line, which was never answered", () => {
		const path = scratch();
		const spool = Spool.open(path);
		spool.add(event("a"));
		spool.close();
		appendFileSync(path, '{"op":"add","id":"b","tar');

		const reopened = Spool.open(path);
		expect(reopened.list().map((e) => e.id)).toEqual(["a"]);
		reopened.add(event("c"));
		reopened.close();
		expect(Spool.open(path).list().map((e) => e.id)).toEqual(["a", "c"]);
	});

	it("rewrites the file once accepted events pile up", () => {
		const path = scratch();
		const spool = Spool.open(path);
		spool.add(event("keep"));
		for (let i = 0; i < 250; i++) {
			spool.add(event(`e${i}`));
			spool.done(`e${i}`);
		}
		spool.close();
		const lines = readFileSync(path, "utf8").trim().split("\n");
		expect(lines.length).toBeLessThan(150);
		expect(Spool.open(path).list().map((e) => e.id)).toEqual(["keep"]);
	});
});
