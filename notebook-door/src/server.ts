// The door's MCP endpoint: streamable HTTP, one JSON-RPC request per POST, answered with plain JSON.
import { timingSafeEqual } from "node:crypto";
import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import type { Grant } from "./grants.ts";
import { Refused } from "./grants.ts";
import type { Notebook } from "./notebook.ts";

export const PROTOCOL_VERSION = "2025-06-18";
const MAX_BODY = 2 * 1024 * 1024;

type Tool = {
	readonly name: string;
	readonly description: string;
	readonly inputSchema: Record<string, unknown>;
	readonly writes: boolean;
};

const str = (description: string) => ({ type: "string", description });

const TOOLS: readonly Tool[] = [
	{
		name: "list",
		description: "List the notes and folders in a folder that your grant can see. `` is the Notebook root.",
		inputSchema: { type: "object", properties: { folder: str("A folder, such as `Fields/Galley/`") }, required: ["folder"] },
		writes: false,
	},
	{
		name: "search",
		description: "Find notes in your grant whose path or text contains every word of the query.",
		inputSchema: { type: "object", properties: { query: str("Words to find") }, required: ["query"] },
		writes: false,
	},
	{
		name: "read",
		description: "Read a note. Returns its text and the hash an update must carry.",
		inputSchema: { type: "object", properties: { path: str("The note's path, such as `Fields/Galley/Galley.md`") }, required: ["path"] },
		writes: false,
	},
	{
		name: "create_note",
		description: "Create a note inside your write scope. Fails if a note exists at the path.",
		inputSchema: {
			type: "object",
			properties: { path: str("The new note's path"), text: str("The whole note, frontmatter first"), message: str("The commit message") },
			required: ["path", "text", "message"],
		},
		writes: true,
	},
	{
		name: "update_note",
		description: "Replace a note's text. Refused if the note changed since you read it; read it again and redo the change.",
		inputSchema: {
			type: "object",
			properties: {
				path: str("The note's path"),
				text: str("The whole new text"),
				hash: str("The hash `read` returned"),
				message: str("The commit message"),
			},
			required: ["path", "text", "hash", "message"],
		},
		writes: true,
	},
];

/** The tools a grant has. A read-only caller has no write tool at all. */
export function toolsFor(grant: Grant): readonly Tool[] {
	return TOOLS.filter((t) => !t.writes || grant.mode === "read-write");
}

type Rpc = { jsonrpc: "2.0"; id?: string | number | null; method: string; params?: Record<string, unknown> };

export function startServer(options: {
	readonly host: string;
	readonly port: number;
	readonly notebook: Notebook;
	/** Each caller's token and grant. */
	readonly callers: readonly { readonly token: string; readonly grant: Grant }[];
	readonly log: (message: string) => void;
}): Promise<Server> {
	const callerOf = (request: IncomingMessage): Grant | undefined => {
		const header = request.headers.authorization;
		const token = typeof header === "string" && header.startsWith("Bearer ") ? header.slice(7) : undefined;
		if (token === undefined) {
			return undefined;
		}
		let found: Grant | undefined;
		for (const caller of options.callers) {
			const a = Buffer.from(caller.token);
			const b = Buffer.from(token);
			if (a.length === b.length && timingSafeEqual(a, b)) {
				found = caller.grant;
			}
		}
		return found;
	};

	const server = createServer((request, response) => {
		handle(request, response).catch((error: unknown) => {
			options.log(`error: ${error instanceof Error ? error.message : String(error)}`);
			if (!response.headersSent) {
				json(response, 500, { error: "internal error" });
			}
		});
	});

	async function handle(request: IncomingMessage, response: ServerResponse): Promise<void> {
		if (request.url !== "/mcp") {
			return json(response, 404, { error: "not found" });
		}
		if (request.method !== "POST") {
			response.writeHead(405, { allow: "POST" }).end();
			return;
		}
		const grant = callerOf(request);
		if (grant === undefined) {
			return json(response, 401, { error: "unknown token" });
		}
		const body = await readBody(request);
		if (body === undefined) {
			return json(response, 413, { error: "request too large" });
		}
		let rpc: Rpc;
		try {
			rpc = JSON.parse(body) as Rpc;
		} catch {
			return json(response, 400, { jsonrpc: "2.0", id: null, error: { code: -32700, message: "parse error" } });
		}
		if (rpc.id === undefined) {
			// A notification, such as notifications/initialized: nothing to answer.
			response.writeHead(202).end();
			return;
		}
		const reply = (result: unknown) => json(response, 200, { jsonrpc: "2.0", id: rpc.id, result });
		const fail = (code: number, message: string) => json(response, 200, { jsonrpc: "2.0", id: rpc.id, error: { code, message } });

		switch (rpc.method) {
			case "initialize":
				return reply({
					protocolVersion: PROTOCOL_VERSION,
					capabilities: { tools: {} },
					serverInfo: { name: "notebook-door", version: "0.1.0" },
					instructions: `You are ${grant.caller}. Notes follow the Notebook's CLAUDE.md.`,
				});
			case "ping":
				return reply({});
			case "tools/list":
				return reply({ tools: toolsFor(grant).map(({ writes: _, ...tool }) => tool) });
			case "tools/call": {
				const name = String(rpc.params?.name ?? "");
				const args = (rpc.params?.arguments ?? {}) as Record<string, unknown>;
				if (!toolsFor(grant).some((t) => t.name === name)) {
					return fail(-32602, `no tool ${name} for ${grant.caller}`);
				}
				try {
					const result = await call(options.notebook, grant, name, args);
					return reply({ content: [{ type: "text", text: JSON.stringify(result) }], structuredContent: result, isError: false });
				} catch (error) {
					if (error instanceof Refused) {
						options.log(`${grant.caller} ${name}: ${error.message}`);
						return reply({
							content: [{ type: "text", text: error.message }],
							structuredContent: { refused: error.message, retry: error.name === "Behind" },
							isError: true,
						});
					}
					throw error;
				}
			}
			default:
				return fail(-32601, `no method ${rpc.method}`);
		}
	}

	return new Promise((resolve, reject) => {
		server.once("error", reject);
		server.listen(options.port, options.host, () => {
			server.off("error", reject);
			resolve(server);
		});
	});
}

async function call(notebook: Notebook, grant: Grant, name: string, args: Record<string, unknown>): Promise<Record<string, unknown>> {
	const text = (key: string) => {
		const value = args[key];
		if (typeof value !== "string") {
			throw new Refused(`${name} needs ${key}`);
		}
		return value;
	};
	switch (name) {
		case "list":
			return notebook.list(grant, text("folder"));
		case "search":
			return { results: notebook.search(grant, text("query")) };
		case "read":
			return notebook.read(grant, text("path"));
		case "create_note":
			return notebook.create(grant, text("path"), text("text"), text("message"));
		case "update_note":
			return notebook.update(grant, text("path"), text("text"), text("hash"), text("message"));
		default:
			throw new Refused(`no tool ${name}`);
	}
}

async function readBody(request: IncomingMessage): Promise<string | undefined> {
	const chunks: Buffer[] = [];
	let size = 0;
	for await (const chunk of request) {
		size += (chunk as Buffer).length;
		if (size > MAX_BODY) {
			return undefined;
		}
		chunks.push(chunk as Buffer);
	}
	return Buffer.concat(chunks).toString("utf8");
}

function json(response: ServerResponse, status: number, body: unknown): void {
	response.writeHead(status, { "content-type": "application/json" }).end(JSON.stringify(body));
}
