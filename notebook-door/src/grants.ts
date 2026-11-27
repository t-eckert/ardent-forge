// Who may read and write what. See README.md, "Grants and the deny list".
import { createHash } from "node:crypto";

/** One caller's grant: the folders and notes it may read, and the narrower set it may write. */
export type Grant = {
	/** The caller's name, used in commit messages and logs, such as `stet.digest`. */
	readonly caller: string;
	/** The git author its writes are committed as, such as `stet <stet@agents>`. */
	readonly author: string;
	readonly mode: "read-only" | "read-write";
	/** Folders end in `/`; anything else names one note. Paths are relative to the Notebook root. */
	readonly read: readonly string[];
	readonly write: readonly string[];
	/** May create new notes directly in the Notebook root, the inbox for notes the caller is unsure where to file. */
	readonly rootInbox?: boolean;
	/** Notes it writes under these folders must have a `## Reference` section, as research notes do. */
	readonly requireReference?: readonly string[];
	/** The value `author:` must have in the frontmatter of notes it creates, such as `stet`. */
	readonly frontmatterAuthor: string;
};

export type DoorConfig = {
	/** The Notebook checkout, `/data/ardent-forge/notebook`. */
	readonly notebook: string;
	/** Notes no grant can reach, by path. Notes with `private: true` in their frontmatter are denied as well. */
	readonly deny: readonly string[];
	/** Each caller's grant, keyed by the name of the environment variable holding its token. */
	readonly grants: Readonly<Record<string, Grant>>;
};

export class Refused extends Error {
	constructor(message: string) {
		super(message);
		this.name = "Refused";
	}
}

/**
 * A note's path, normalized and checked: relative, inside the Notebook, a Markdown file, never in a dot directory.
 * Throws `Refused` for anything else.
 */
export function notePath(raw: string): string {
	const path = raw.replace(/\\/g, "/").replace(/^\.\//, "");
	const parts = path.split("/");
	if (
		path === "" ||
		path.startsWith("/") ||
		parts.some((p) => p === "" || p === "." || p === ".." || p.startsWith(".")) ||
		!path.endsWith(".md") ||
		path.includes("\0")
	) {
		throw new Refused(`not a note path: ${raw}`);
	}
	return path;
}

/** A folder path for listing: relative, ending in `/`, or `` for the root. */
export function folderPath(raw: string): string {
	const path = raw.replace(/\\/g, "/").replace(/^\.\//, "").replace(/\/?$/, "/");
	if (path === "/") {
		return "";
	}
	const parts = path.slice(0, -1).split("/");
	if (path.startsWith("/") || parts.some((p) => p === "" || p === "." || p === ".." || p.startsWith("."))) {
		throw new Refused(`not a folder path: ${raw}`);
	}
	return path;
}

function inScope(path: string, scope: readonly string[]): boolean {
	return scope.some((entry) => (entry.endsWith("/") ? path.startsWith(entry) : path === entry));
}

/** Whether the frontmatter at the top of `text` sets `private: true`. */
export function isPrivate(text: string): boolean {
	const frontmatter = /^---\r?\n([\s\S]*?)\r?\n---/.exec(text);
	return frontmatter !== null && /^private:\s*true\s*$/m.test(frontmatter[1] ?? "");
}

/** Denied by path, whatever the note says. The private flag is checked where the text is read. */
export function deniedByPath(config: DoorConfig, path: string): boolean {
	return config.deny.includes(path);
}

export function mayRead(grant: Grant, path: string): boolean {
	return inScope(path, grant.read) || mayWrite(grant, path);
}

export function mayWrite(grant: Grant, path: string): boolean {
	if (grant.mode !== "read-write") {
		return false;
	}
	return inScope(path, grant.write);
}

/** Whether the caller may create `path` in the Notebook root. Only new notes, never an update. */
export function mayCreateInRoot(grant: Grant, path: string): boolean {
	return grant.mode === "read-write" && grant.rootInbox === true && !path.includes("/");
}

/** Whether a folder could hold anything the grant may read, so listing it is allowed. */
export function mayList(grant: Grant, folder: string): boolean {
	const scopes = [...grant.read, ...grant.write];
	return scopes.some((entry) => entry.startsWith(folder) || (entry.endsWith("/") && folder.startsWith(entry)));
}

/** The hash an update carries: SHA-256 of the note's bytes as read. */
export function hashText(text: string): string {
	return createHash("sha256").update(text, "utf8").digest("hex");
}

/** Checks a loaded config, so a typo fails the start rather than a request. */
export function checkConfig(config: DoorConfig): void {
	for (const path of config.deny) {
		notePath(path);
	}
	for (const [variable, grant] of Object.entries(config.grants)) {
		for (const entry of [...grant.read, ...grant.write]) {
			if (entry.endsWith("/")) {
				folderPath(entry);
			} else {
				notePath(entry);
			}
		}
		if (grant.mode === "read-only" && (grant.write.length > 0 || grant.rootInbox === true)) {
			throw new Error(`${variable}: a read-only grant cannot write`);
		}
	}
}
