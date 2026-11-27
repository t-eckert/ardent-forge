import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import type { AddressInfo } from "node:net";
import type { JsonObject } from "@earendil-works/pi-durable";
import { BodyTooLarge, HANDOFF_PATH, HEADERS, header, readBody } from "./handoff.ts";
import { verifyLinearSignature } from "./linear.ts";

/** An event as the owning process receives it from the gateway, after its own signature check. */
export type Delivery = {
	readonly id: string;
	readonly source: "linear";
	readonly receivedAt: number;
	readonly event: JsonObject;
};

export type InboxOptions = {
	readonly port: number;
	/** This process's Linear webhook signing secret. Without one, every Linear event is refused. */
	readonly linearSecret: string | undefined;
	/** Durably records the delivery, once per id. The inbox answers `202` only after this resolves. */
	readonly accept: (delivery: Delivery) => Promise<void>;
	readonly log: (message: string) => void;
};

/**
 * A job process's end of the hand-off: `POST /events` on localhost. See src/handoff.ts for the protocol.
 *
 * It answers `503` until `open()` and again after `drain()`, so the gateway keeps events in its spool while the job
 * starts or exits. It checks the sender's signature again, but not the timestamp: an event may have waited in the
 * spool for as long as the job was down.
 */
export class Inbox {
	private accepting = false;

	private constructor(
		private readonly options: InboxOptions,
		private readonly server: Server,
	) {}

	static async start(options: InboxOptions): Promise<Inbox> {
		const server = createServer();
		const inbox = new Inbox(options, server);
		server.on("request", (request, response) => {
			inbox.receive(request, response).catch((error: unknown) => {
				options.log(`inbox: ${error instanceof Error ? error.message : String(error)}`);
				if (!response.headersSent) {
					respond(response, 503);
				}
			});
		});
		await new Promise<void>((resolve, reject) => {
			server.once("error", reject);
			server.listen(options.port, "127.0.0.1", () => {
				server.off("error", reject);
				resolve();
			});
		});
		return inbox;
	}

	get port(): number {
		return (this.server.address() as AddressInfo).port;
	}

	/** Start taking events. */
	open(): void {
		this.accepting = true;
	}

	/** Stop taking events: from now on the gateway is told to come back later. */
	drain(): void {
		this.accepting = false;
	}

	async stop(): Promise<void> {
		this.drain();
		const closed = new Promise<void>((resolve) => this.server.close(() => resolve()));
		this.server.closeIdleConnections();
		await closed;
	}

	private async receive(request: IncomingMessage, response: ServerResponse): Promise<void> {
		if (request.url !== HANDOFF_PATH) {
			return respond(response, 404);
		}
		if (request.method !== "POST") {
			return respond(response, 405);
		}
		if (!this.accepting) {
			return respond(response, 503);
		}

		let body: Buffer;
		try {
			body = await readBody(request);
		} catch (error) {
			if (error instanceof BodyTooLarge) {
				return respond(response, 413);
			}
			throw error;
		}
		const id = header(request, HEADERS.deliveryId);
		const source = header(request, HEADERS.source);
		const receivedAt = Number(header(request, HEADERS.receivedAt));
		if (id === undefined || source !== "linear" || !Number.isFinite(receivedAt)) {
			return respond(response, 400);
		}
		const secret = this.options.linearSecret;
		if (secret === undefined || !verifyLinearSignature(body, header(request, HEADERS.linearSignature), secret)) {
			this.options.log(`inbox: refused ${id}: bad signature`);
			return respond(response, 401);
		}
		let event: unknown;
		try {
			event = JSON.parse(body.toString("utf8"));
		} catch {
			return respond(response, 400);
		}
		if (typeof event !== "object" || event === null || Array.isArray(event)) {
			return respond(response, 400);
		}

		// Checked again after the body is read: a drain that started meanwhile wins, and the gateway retries later.
		if (!this.accepting) {
			return respond(response, 503);
		}
		await this.options.accept({ id, source, receivedAt, event: event as JsonObject });
		respond(response, 202);
	}
}

function respond(response: ServerResponse, status: number): void {
	response.writeHead(status, { "content-type": "text/plain" }).end();
}
