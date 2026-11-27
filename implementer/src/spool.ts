import { closeSync, existsSync, fsyncSync, openSync, readFileSync, renameSync, writeSync } from "node:fs";
import { dirname } from "node:path";
import type { ProcessName } from "./processes.ts";

/** One verified webhook, as the gateway received it and as it is handed to the process that owns it. */
export type SpooledEvent = {
	/** The sender's delivery id, such as Linear's `Linear-Delivery`. The owning process deduplicates on it. */
	readonly id: string;
	readonly target: ProcessName;
	readonly source: "linear";
	readonly receivedAt: number;
	/** The sender's signature header, passed through so the owning process can verify the event itself. */
	readonly signature: string;
	/** The raw body, base64, so the bytes the signature covers survive the round trip exactly. */
	readonly body: string;
};

type Line =
	| ({ readonly op: "add" } & SpooledEvent)
	| { readonly op: "done"; readonly id: string }
	| { readonly op: "rejected"; readonly id: string; readonly status: number };

/** Rewrite the file once this many settled lines have built up, and they outnumber the pending events. */
const COMPACT_AFTER = 200;

/**
 * The gateway's spool: an append-only file of verified events not yet accepted by the process that owns them.
 *
 * An event is appended and fsynced before the gateway answers the sender, so an answered event is never lost.
 * Accepting one appends a `done` line. Once settled lines pile up, the file is rewritten with only the pending events,
 * through a temporary file and a rename, so a crash mid-rewrite leaves either the old file or the new one.
 *
 * A crash mid-append can leave a torn last line. It was never fsynced, so the sender was never answered, and it is
 * dropped on open.
 */
export class Spool {
	private fd: number;
	private readonly pending = new Map<string, SpooledEvent>();
	private settled = 0;

	private constructor(private readonly path: string) {
		if (existsSync(path)) {
			this.load(readFileSync(path, "utf8"));
		}
		// Rewrite on open: it drops a torn line and settled history, so appends always start on a clean line.
		this.fd = this.rewrite();
	}

	static open(path: string): Spool {
		return new Spool(path);
	}

	/** Durably records `event`. An id already pending is not added twice. Returns whether it was new. */
	add(event: SpooledEvent): boolean {
		if (this.pending.has(event.id)) {
			return false;
		}
		this.append({ op: "add", ...event });
		this.pending.set(event.id, event);
		return true;
	}

	/** The owning process accepted the event. */
	done(id: string): void {
		this.settle({ op: "done", id });
	}

	/** The owning process refused the event for good, so retrying cannot help. */
	rejected(id: string, status: number): void {
		this.settle({ op: "rejected", id, status });
	}

	/** The oldest pending event for `target`, in the order they arrived. */
	next(target: ProcessName): SpooledEvent | undefined {
		for (const event of this.pending.values()) {
			if (event.target === target) {
				return event;
			}
		}
		return undefined;
	}

	/** Every pending event, oldest first. */
	list(): readonly SpooledEvent[] {
		return [...this.pending.values()];
	}

	close(): void {
		closeSync(this.fd);
	}

	private settle(line: Line & { op: "done" | "rejected" }): void {
		if (!this.pending.delete(line.id)) {
			return;
		}
		this.append(line);
		this.settled++;
		if (this.settled >= COMPACT_AFTER && this.settled > this.pending.size) {
			closeSync(this.fd);
			this.fd = this.rewrite();
		}
	}

	private append(line: Line): void {
		writeSync(this.fd, `${JSON.stringify(line)}\n`);
		fsyncSync(this.fd);
	}

	private load(text: string): void {
		// Every complete line ends in a newline, so the last piece is either empty or a torn append. Drop it either way.
		for (const raw of text.split("\n").slice(0, -1)) {
			if (raw === "") {
				continue;
			}
			const line = JSON.parse(raw) as Line;
			if (line.op === "add") {
				const { op: _, ...event } = line;
				this.pending.set(event.id, event);
			} else {
				this.pending.delete(line.id);
			}
		}
	}

	/** Writes only the pending events to a fresh file, swaps it in, and returns a descriptor open for appending. */
	private rewrite(): number {
		const temporary = `${this.path}.tmp`;
		const fd = openSync(temporary, "w", 0o600);
		for (const event of this.pending.values()) {
			writeSync(fd, `${JSON.stringify({ op: "add", ...event })}\n`);
		}
		fsyncSync(fd);
		closeSync(fd);
		renameSync(temporary, this.path);
		const dir = openSync(dirname(this.path), "r");
		try {
			fsyncSync(dir);
		} finally {
			closeSync(dir);
		}
		this.settled = 0;
		return openSync(this.path, "a", 0o600);
	}
}
