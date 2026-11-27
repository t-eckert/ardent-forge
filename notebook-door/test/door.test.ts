import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { after, describe, it } from "node:test";
import type { DoorConfig, Grant } from "../src/grants.ts";
import { Notebook, type Run, run } from "../src/notebook.ts";
import { startServer } from "../src/server.ts";

const digest: Grant = {
	caller: "stet.digest",
	author: "stet <stet@agents>",
	mode: "read-write",
	read: ["Fields/Galley/", "Projects/Galley/"],
	write: ["Fields/Galley/Work Reports/"],
	rootInbox: true,
	frontmatterAuthor: "stet",
};
const intake: Grant = {
	caller: "stet.intake",
	author: "stet <stet@agents>",
	mode: "read-only",
	read: ["Fields/Galley/Feedback.md"],
	write: [],
	frontmatterAuthor: "stet",
};

const note = (body: string, extra = "") => `---\ntype: report\nfield: Galley\ncreated: 2026-11-28\nauthor: stet\n${extra}---\n\n${body}\n`;

/** A Notebook checkout with an upstream, and a syncshot stand-in that records its calls and commits for real. */
function scene() {
	const base = mkdtempSync(join(tmpdir(), "door-"));
	const upstream = join(base, "upstream.git");
	const root = join(base, "notebook");
	const git = (cwd: string, ...args: string[]) => execFileSync("git", args, { cwd, encoding: "utf8" });
	execFileSync("git", ["init", "--quiet", "--bare", "--initial-branch=main", upstream]);
	execFileSync("git", ["clone", "--quiet", upstream, root]);
	git(root, "config", "user.name", "Ardent Forge");
	git(root, "config", "user.email", "forge@example");
	const files: Record<string, string> = {
		"Fields/Galley/Galley.md": note("Galley's home note"),
		"Fields/Galley/Feedback.md": note("feedback from beta partners"),
		"Fields/Galley/HR Disclosure Email.md": note("galley disclosure"),
		"Fields/Galley/Secret Plan.md": note("galley secret", "private: true\n"),
		"Fields/Galley/Work Reports/2026-11-21 Saturday Digest.md": note("last week"),
		"Log/2026-11-27.md": note("galley in the log"),
	};
	for (const [path, text] of Object.entries(files)) {
		mkdirSync(dirname(join(root, path)), { recursive: true });
		writeFileSync(join(root, path), text);
	}
	git(root, "add", ".");
	git(root, "commit", "--quiet", "-m", "seed");
	git(root, "push", "--quiet", "-u", "origin", "main");

	const calls: string[][] = [];
	const fakeRun: Run = async (command, args, cwd) => {
		if (command === "python3") {
			const [, verb, ...rest] = args;
			calls.push([verb as string, ...rest]);
			if (verb === "commit") {
				const author = rest[rest.indexOf("--author") + 1] as string;
				const message = rest[rest.indexOf("-m") + 1] as string;
				const path = rest[rest.indexOf("--") + 1] as string;
				git(cwd, "add", "--", path);
				git(cwd, "commit", "--quiet", "--author", author, "-m", message, "--", path);
			}
			return { code: 0, stdout: "", stderr: "" };
		}
		return run(command, args, cwd);
	};
	const config: DoorConfig = {
		notebook: root,
		deny: ["Fields/Galley/HR Disclosure Email.md"],
		grants: { STET_DIGEST_TOKEN: digest, STET_INTAKE_TOKEN: intake },
	};
	const notebook = new Notebook({ config, syncshot: "/syncshot.py", scratch: join(base, "scratch"), run: fakeRun });
	return { root, upstream, base, git, notebook, calls };
}

describe("grants and the deny list", () => {
	it("keeps each caller inside its grant", () => {
		const { notebook } = scene();
		assert.match(notebook.read(intake, "Fields/Galley/Feedback.md").text, /beta partners/);
		assert.throws(() => notebook.read(intake, "Fields/Galley/Galley.md"), /outside stet.intake's grant/);
		assert.throws(() => notebook.read(digest, "Log/2026-11-27.md"), /outside/);
		assert.throws(() => notebook.read(digest, "../etc/passwd.md"), /not a note path/);
		assert.throws(() => notebook.list(intake, "Log/"), /outside/);
	});

	it("never names a denied or private note, in read, list or search", () => {
		const { notebook } = scene();
		assert.throws(() => notebook.read(digest, "Fields/Galley/HR Disclosure Email.md"), /no note at/);
		assert.throws(() => notebook.read(digest, "Fields/Galley/Secret Plan.md"), /no note at/);
		const listed = notebook.list(digest, "Fields/Galley/");
		assert.deepEqual(listed.notes, ["Fields/Galley/Feedback.md", "Fields/Galley/Galley.md"]);
		assert.deepEqual(listed.folders, ["Fields/Galley/Work Reports/"]);
		const found = notebook.search(digest, "galley").map((r) => r.path);
		assert.ok(!found.some((p) => p.includes("Disclosure") || p.includes("Secret") || p.startsWith("Log/")), found.join());
	});

	it("gives a read-only caller no way to write", async () => {
		const { notebook } = scene();
		await assert.rejects(notebook.create(intake, "Fields/Galley/New.md", note("x"), "m"), /may not create/);
	});
});

describe("writes", () => {
	it("creates a note under a lease, committed with stet as the author", async () => {
		const { notebook, root, git, calls } = scene();
		const path = "Fields/Galley/Work Reports/2026-11-28 Saturday Digest.md";
		await notebook.create(digest, path, note("this week"), "Write the Saturday digest");
		assert.match(readFileSync(join(root, path), "utf8"), /this week/);
		assert.equal(git(root, "log", "-1", "--format=%an <%ae>|%cn", "--", path).trim(), "stet <stet@agents>|Ardent Forge");
		assert.deepEqual(
			calls.map((c) => c[0]),
			["pause", "commit", "resume"],
		);
		await assert.rejects(notebook.create(digest, path, note("again"), "m"), /already exists/);
	});

	it("refuses an update whose hash is stale, and takes one whose hash matches", async () => {
		const { notebook, root } = scene();
		const path = "Fields/Galley/Work Reports/2026-11-21 Saturday Digest.md";
		const read = notebook.read(digest, path);
		writeFileSync(join(root, path), note("Thomas edited this meanwhile"));
		await assert.rejects(notebook.update(digest, path, note("stet's change"), read.hash, "m"), /changed since it was read/);
		const again = notebook.read(digest, path);
		await notebook.update(digest, path, note("stet's change"), again.hash, "Update the digest");
		assert.match(readFileSync(join(root, path), "utf8"), /stet's change/);
	});

	it("refuses a write while GitHub has a newer version of the note", async () => {
		const { notebook, upstream, base, git } = scene();
		const other = join(base, "mac");
		execFileSync("git", ["clone", "--quiet", upstream, other]);
		git(other, "config", "user.name", "Mac");
		git(other, "config", "user.email", "mac@example");
		const path = "Fields/Galley/Work Reports/2026-11-21 Saturday Digest.md";
		writeFileSync(join(other, path), note("edited on the Mac"));
		git(other, "commit", "--quiet", "-am", "mac edit");
		git(other, "push", "--quiet");
		const read = notebook.read(digest, path);
		await assert.rejects(notebook.update(digest, path, note("stet"), read.hash, "m"), /newer version/);
	});

	it("checks the Notebook's conventions and the markdown rule before writing", async () => {
		const { notebook } = scene();
		const dir = "Fields/Galley/Work Reports/";
		await assert.rejects(notebook.create(digest, `${dir}2026-11-28 A.md`, "no frontmatter\n", "m"), /no frontmatter/);
		await assert.rejects(notebook.create(digest, `${dir}2026-11-28 B.md`, note("x").replace("author: stet\n", ""), "m"), /author: stet/);
		await assert.rejects(notebook.create(digest, `${dir}2026-11-28 C.md`, note("done ✅"), "m"), /emoji/);
		await assert.rejects(notebook.create(digest, `${dir}2026-11-28 D.md`, note("![x](https://evil.example/?d=1)"), "m"), /image embed/);
		await assert.rejects(notebook.create(digest, `${dir}2026-11-28 E.md`, note("<img src=x>"), "m"), /raw HTML/);
		await assert.rejects(notebook.create(digest, `${dir}2026-11-28 F.md`, note("[a](javascript:alert(1))"), "m"), /javascript/);
		await notebook.create(digest, "Unsure Where This Goes.md", note("for the inbox"), "m");
		await assert.rejects(notebook.update(digest, "Unsure Where This Goes.md", note("y"), "h", "m"), /may not update/);
	});
});

describe("the MCP endpoint", () => {
	const servers: { close: () => void }[] = [];
	after(() => servers.forEach((s) => s.close()));

	it("authenticates each caller and offers a read-only one no write tools", async () => {
		const { notebook } = scene();
		const tokens = { digest: "d".repeat(40), intake: "i".repeat(40) };
		const server = await startServer({
			host: "127.0.0.1",
			port: 0,
			notebook,
			callers: [
				{ token: tokens.digest, grant: digest },
				{ token: tokens.intake, grant: intake },
			],
			log: () => {},
		});
		servers.push(server);
		const port = (server.address() as { port: number }).port;
		const rpc = (token: string | undefined, method: string, params?: unknown) =>
			fetch(`http://127.0.0.1:${port}/mcp`, {
				method: "POST",
				headers: { "content-type": "application/json", ...(token === undefined ? {} : { authorization: `Bearer ${token}` }) },
				body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
			});

		assert.equal((await rpc(undefined, "tools/list")).status, 401);
		assert.equal((await rpc("x".repeat(40), "tools/list")).status, 401);
		const intakeTools = (await (await rpc(tokens.intake, "tools/list")).json()) as { result: { tools: { name: string }[] } };
		assert.deepEqual(intakeTools.result.tools.map((t) => t.name), ["list", "search", "read"]);
		const digestTools = (await (await rpc(tokens.digest, "tools/list")).json()) as { result: { tools: { name: string }[] } };
		assert.ok(digestTools.result.tools.some((t) => t.name === "update_note"));

		const refused = (await (
			await rpc(tokens.intake, "tools/call", { name: "create_note", arguments: { path: "a.md", text: "x", message: "m" } })
		).json()) as { error?: { message: string } };
		assert.match(refused.error?.message ?? "", /no tool create_note/);
		const read = (await (await rpc(tokens.intake, "tools/call", { name: "read", arguments: { path: "Fields/Galley/Feedback.md" } })).json()) as {
			result: { structuredContent: { hash: string }; isError: boolean };
		};
		assert.equal(read.result.isError, false);
		assert.match(read.result.structuredContent.hash, /^[0-9a-f]{64}$/);
	});
});

describe("updates keep a note's own shape", () => {
	it("updates a note without the creation frontmatter, but still checks the markdown rule", async () => {
		const { notebook, root, git } = scene();
		const path = "Fields/Galley/Work Reports/old-slug.md";
		writeFileSync(join(root, path), "**URL:** https://example.org\n\nAn older profile.\n");
		git(root, "add", ".");
		git(root, "commit", "--quiet", "-m", "old");
		git(root, "push", "--quiet");
		const read = notebook.read(digest, path);
		await notebook.update(digest, path, "**URL:** https://example.org\n\nRefreshed.\n", read.hash, "m");
		const again = notebook.read(digest, path);
		await assert.rejects(notebook.update(digest, path, "![x](https://evil.example/a.png)\n", again.hash, "m"), /image embed/);
	});
});
