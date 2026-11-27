// The door's operations on the Notebook checkout: list, search, read, create and update. No delete, no move.
import { execFile } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, readFileSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import { join, posix } from "node:path";
import { writeRefusals } from "./checks.ts";
import {
	type DoorConfig,
	deniedByPath,
	folderPath,
	type Grant,
	hashText,
	isPrivate,
	mayCreateInRoot,
	mayList,
	mayRead,
	mayWrite,
	notePath,
	Refused,
} from "./grants.ts";

/** Runs a command and resolves with its exit code and output. Tests replace it. */
export type Run = (command: string, args: readonly string[], cwd: string) => Promise<{ code: number; stdout: string; stderr: string }>;

export const run: Run = (command, args, cwd) =>
	new Promise((resolve) => {
		execFile(command, args, { cwd, timeout: 120_000, maxBuffer: 8 * 1024 * 1024 }, (error, stdout, stderr) => {
			const code = error === null ? 0 : typeof error.code === "number" ? error.code : 1;
			resolve({ code, stdout: String(stdout), stderr: String(stderr) });
		});
	});

/** A write refused only because the checkout is behind GitHub. The caller retries once syncshot has caught up. */
export class Behind extends Refused {
	constructor(path: string) {
		super(`GitHub has a newer version of ${path} than the Forge's checkout; retry once syncshot has caught up`);
		this.name = "Behind";
	}
}

const LEASE_OWNER = "notebook-door";
const SEARCH_LIMIT = 20;

export type NotebookOptions = {
	readonly config: DoorConfig;
	/** Where `syncshot.py` is. */
	readonly syncshot: string;
	/** A directory on the Notebook's filesystem, outside its tree, for writing a note before renaming it in. */
	readonly scratch: string;
	readonly run?: Run;
	readonly log?: (message: string) => void;
};

export class Notebook {
	readonly #options: NotebookOptions;
	readonly #run: Run;
	/** Writes go one at a time, so two never hold the lease and move files at once. */
	#writes: Promise<unknown> = Promise.resolve();

	constructor(options: NotebookOptions) {
		this.#options = options;
		this.#run = options.run ?? run;
	}

	get #root(): string {
		return this.#options.config.notebook;
	}

	/** Whether a note is hidden from this caller: outside its grant, on the deny list, or marked private. */
	#hidden(grant: Grant, path: string, text?: string): boolean {
		if (!mayRead(grant, path) || deniedByPath(this.#options.config, path)) {
			return true;
		}
		const body = text ?? this.#text(path);
		return body !== undefined && isPrivate(body);
	}

	#text(path: string): string | undefined {
		const file = join(this.#root, path);
		return existsSync(file) && statSync(file).isFile() ? readFileSync(file, "utf8") : undefined;
	}

	/** The notes and folders in `folder` this caller may see. A denied note is not named. */
	list(grant: Grant, rawFolder: string): { readonly folders: string[]; readonly notes: string[] } {
		const folder = folderPath(rawFolder);
		if (!mayList(grant, folder)) {
			throw new Refused(`${folder || "the Notebook root"} is outside ${grant.caller}'s grant`);
		}
		const dir = join(this.#root, folder);
		if (!existsSync(dir)) {
			return { folders: [], notes: [] };
		}
		const folders: string[] = [];
		const notes: string[] = [];
		for (const entry of readdirSync(dir, { withFileTypes: true })) {
			if (entry.name.startsWith(".")) {
				continue;
			}
			const path = `${folder}${entry.name}`;
			if (entry.isDirectory()) {
				if (mayList(grant, `${path}/`)) {
					folders.push(`${path}/`);
				}
			} else if (entry.name.endsWith(".md") && !this.#hidden(grant, path)) {
				notes.push(path);
			}
		}
		return { folders: folders.sort(), notes: notes.sort() };
	}

	/** Notes in the caller's grant whose path or text contains every word of `query`, with a line of context. */
	search(grant: Grant, query: string): { readonly path: string; readonly line: string }[] {
		const words = query.toLowerCase().split(/\s+/).filter((w) => w !== "");
		if (words.length === 0) {
			throw new Refused("search needs a query");
		}
		const found: { path: string; line: string }[] = [];
		const seen = new Set<string>();
		for (const entry of [...grant.read, ...grant.write]) {
			for (const path of entry.endsWith("/") ? this.#walk(entry) : [entry]) {
				if (seen.has(path) || found.length >= SEARCH_LIMIT) {
					continue;
				}
				seen.add(path);
				const text = this.#text(path);
				if (text === undefined || this.#hidden(grant, path, text)) {
					continue;
				}
				const haystack = `${path}\n${text}`.toLowerCase();
				if (words.every((w) => haystack.includes(w))) {
					const line = text.split("\n").find((l) => words.some((w) => l.toLowerCase().includes(w))) ?? "";
					found.push({ path, line: line.trim().slice(0, 200) });
				}
			}
		}
		return found;
	}

	#walk(folder: string): string[] {
		const dir = join(this.#root, folder);
		if (!existsSync(dir)) {
			return [];
		}
		const paths: string[] = [];
		for (const entry of readdirSync(dir, { withFileTypes: true })) {
			if (entry.name.startsWith(".")) {
				continue;
			}
			const path = `${folder}${entry.name}`;
			if (entry.isDirectory()) {
				paths.push(...this.#walk(`${path}/`));
			} else if (entry.name.endsWith(".md")) {
				paths.push(path);
			}
		}
		return paths.sort();
	}

	/** A note's text and the hash an update must carry. A note the caller may not see does not exist, as far as it knows. */
	read(grant: Grant, rawPath: string): { readonly path: string; readonly text: string; readonly hash: string } {
		const path = notePath(rawPath);
		const text = this.#text(path);
		if (text === undefined || this.#hidden(grant, path, text)) {
			throw new Refused(mayRead(grant, path) ? `no note at ${path}` : `${path} is outside ${grant.caller}'s grant`);
		}
		return { path, text, hash: hashText(text) };
	}

	/** Creates a note. Fails if one exists, so a retried create finds it rather than writing twice. */
	async create(grant: Grant, rawPath: string, text: string, message: string): Promise<{ readonly path: string; readonly hash: string }> {
		const path = notePath(rawPath);
		if (!mayWrite(grant, path) && !mayCreateInRoot(grant, path)) {
			throw new Refused(`${grant.caller} may not create ${path}`);
		}
		if (deniedByPath(this.#options.config, path)) {
			throw new Refused(`${grant.caller} may not create ${path}`);
		}
		this.#check(grant, path, text, true);
		return this.#write(grant, path, text, message, undefined);
	}

	/** Replaces a note's text, if it is still the version whose hash the caller read. */
	async update(grant: Grant, rawPath: string, text: string, readHash: string, message: string): Promise<{ readonly path: string; readonly hash: string }> {
		const path = notePath(rawPath);
		if (!mayWrite(grant, path) || deniedByPath(this.#options.config, path)) {
			throw new Refused(`${grant.caller} may not update ${path}`);
		}
		const current = this.#text(path);
		if (current === undefined || isPrivate(current)) {
			throw new Refused(`no note at ${path}`);
		}
		if (isPrivate(text)) {
			throw new Refused("a note cannot be marked private by an update; Thomas does that");
		}
		this.#check(grant, path, text, false);
		return this.#write(grant, path, text, message, readHash);
	}

	#check(grant: Grant, path: string, text: string, creating: boolean): void {
		const dir = join(this.#root, posix.dirname(path));
		const siblings = existsSync(dir) ? readdirSync(dir).filter((n) => n.endsWith(".md")) : [];
		const refusals = writeRefusals({ grant, path, text, creating, siblings });
		if (refusals.length > 0) {
			throw new Refused(`refused: ${refusals.join("; ")}`);
		}
	}

	#write(grant: Grant, path: string, text: string, message: string, readHash: string | undefined) {
		const next = this.#writes.then(() => this.#underLease(grant, path, text, message, readHash));
		this.#writes = next.catch(() => {});
		return next;
	}

	/**
	 * The write itself, under a syncshot pause lease: fetch, refuse if GitHub is ahead on this note, check the hash or
	 * that the note is new, write through a rename from outside the tree, and commit as the caller. syncshot pushes it
	 * on its next tick. The door never pulls, pushes or commits by itself.
	 */
	async #underLease(grant: Grant, path: string, text: string, message: string, readHash: string | undefined) {
		const root = this.#root;
		const syncshot = (...args: string[]) => this.#run("python3", [this.#options.syncshot, ...args], root);
		const paused = await syncshot("pause", "2m", "--owner", LEASE_OWNER);
		if (paused.code !== 0) {
			throw new Error(`syncshot pause failed: ${paused.stderr.trim()}`);
		}
		try {
			const fetched = await this.#run("git", ["fetch", "--quiet", "origin"], root);
			if (fetched.code !== 0) {
				throw new Error(`git fetch failed: ${fetched.stderr.trim()}`);
			}
			const ahead = await this.#run("git", ["rev-list", "HEAD..@{upstream}", "--", path], root);
			if (ahead.code !== 0) {
				throw new Error(`git rev-list failed: ${ahead.stderr.trim()}`);
			}
			if (ahead.stdout.trim() !== "") {
				throw new Behind(path);
			}

			const current = this.#text(path);
			if (readHash === undefined && current !== undefined) {
				throw new Refused(`a note already exists at ${path}`);
			}
			if (readHash !== undefined && (current === undefined || hashText(current) !== readHash)) {
				throw new Refused(`${path} changed since it was read; read it again and redo the change`);
			}

			mkdirSync(this.#options.scratch, { recursive: true });
			const temporary = join(this.#options.scratch, `${process.pid}-${Date.now()}.md`);
			writeFileSync(temporary, text, { mode: 0o644 });
			try {
				mkdirSync(join(root, posix.dirname(path)), { recursive: true });
				renameSync(temporary, join(root, path));
			} finally {
				rmSync(temporary, { force: true });
			}

			const committed = await syncshot("commit", "--owner", LEASE_OWNER, "--author", grant.author, "-m", message, "--", path);
			if (committed.code !== 0) {
				throw new Error(`syncshot commit failed: ${committed.stderr.trim()}`);
			}
			this.#options.log?.(`${grant.caller} ${readHash === undefined ? "created" : "updated"} ${path}`);
			return { path, hash: hashText(text) };
		} finally {
			await syncshot("resume", "--owner", LEASE_OWNER);
		}
	}
}
