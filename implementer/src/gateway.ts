import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import type { AddressInfo } from "node:net";
import { setTimeout as sleep } from "node:timers/promises";
import { BodyTooLarge, HANDOFF_PATH, HEADERS, header, readBody } from "./handoff.ts";
import { isFreshLinearEvent, verifyLinearSignature } from "./linear.ts";
import { PROCESSES, type ProcessName } from "./processes.ts";
import { Spool, type SpooledEvent } from "./spool.ts";

export type GatewayOptions = {
	readonly spoolPath: string;
	/** The public listener, the only thing `cloudflared` routes to. Always bound to localhost. */
	readonly port: number;
	/** Each owning process's hand-off port on localhost. */
	readonly targets: Partial<Record<ProcessName, number>>;
	/** Each owning process's Linear webhook signing secret. A process with no secret gets no route. */
	readonly linearSecrets: Partial<Record<ProcessName, string>>;
	readonly log: (message: string) => void;
	readonly now?: () => number;
	/** First and longest wait between delivery attempts to a process that is not taking events. */
	readonly retry?: { readonly initialMs: number; readonly maxMs: number };
};

const DEFAULT_RETRY = { initialMs: 1000, maxMs: 30_000 };
const DELIVERY_TIMEOUT_MS = 10_000;
/** Answers a hand-off can give that mean the event will never be accepted, so it is not retried. */
const PERMANENT = new Set([400, 401, 413]);
/** Linear's delivery ids are UUIDs. Anything that does not look like an id is refused rather than spooled. */
const DELIVERY_ID = /^[A-Za-z0-9-]{1,128}$/;

/**
 * The gateway: the only process behind the Cloudflare Tunnel. See docs/design.md, "Hosting".
 *
 * `POST /linear/<process>` checks Linear's signature and the signed timestamp, appends the event to the spool, and only
 * then answers `200`. A worker per owning process hands each spooled event over localhost, oldest first, and retries
 * with backoff until the process accepts it. The gateway makes no other outbound calls.
 */
export class Gateway {
	private readonly stopping = new AbortController();
	private readonly wakers = new Map<ProcessName, () => void>();
	private readonly workers: Promise<void>[] = [];

	private constructor(
		private readonly options: GatewayOptions,
		private readonly spool: Spool,
		private readonly server: Server,
	) {}

	static async start(options: GatewayOptions): Promise<Gateway> {
		const spool = Spool.open(options.spoolPath);
		const server = createServer();
		const gateway = new Gateway(options, spool, server);
		server.on("request", (request, response) => {
			gateway.receive(request, response).catch((error: unknown) => {
				options.log(`gateway: ${error instanceof Error ? error.message : String(error)}`);
				if (!response.headersSent) {
					respond(response, 500);
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
		for (const target of gateway.routes()) {
			gateway.workers.push(gateway.deliver(target));
		}
		const waiting = spool.list().length;
		options.log(`gateway: listening on 127.0.0.1:${gateway.port}, ${waiting} event${waiting === 1 ? "" : "s"} in the spool`);
		return gateway;
	}

	get port(): number {
		return (this.server.address() as AddressInfo).port;
	}

	/** Events not yet accepted by the process that owns them. */
	pending(): readonly SpooledEvent[] {
		return this.spool.list();
	}

	/** Stops taking webhooks, lets in-flight requests finish, stops the workers and closes the spool. */
	async stop(): Promise<void> {
		const closed = new Promise<void>((resolve) => this.server.close(() => resolve()));
		this.server.closeIdleConnections();
		this.stopping.abort();
		for (const wake of this.wakers.values()) {
			wake();
		}
		await Promise.all([closed, ...this.workers]);
		this.spool.close();
	}

	private routes(): ProcessName[] {
		return PROCESSES.filter((p) => this.options.linearSecrets[p] !== undefined && this.options.targets[p] !== undefined);
	}

	private async receive(request: IncomingMessage, response: ServerResponse): Promise<void> {
		const target = PROCESSES.find((p) => request.url === `/linear/${p}`);
		const secret = target === undefined ? undefined : this.options.linearSecrets[target];
		if (target === undefined || secret === undefined || this.options.targets[target] === undefined) {
			return respond(response, 404);
		}
		if (request.method !== "POST") {
			return respond(response, 405);
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
		const signature = header(request, HEADERS.linearSignature);
		if (signature === undefined || !verifyLinearSignature(body, signature, secret)) {
			this.options.log(`gateway: refused a webhook for ${target}: bad signature`);
			return respond(response, 401);
		}
		const id = header(request, "linear-delivery");
		if (id === undefined || !DELIVERY_ID.test(id)) {
			this.options.log(`gateway: refused a webhook for ${target}: no usable Linear-Delivery header`);
			return respond(response, 400);
		}
		let event: unknown;
		try {
			event = JSON.parse(body.toString("utf8"));
		} catch {
			return respond(response, 400);
		}
		const now = (this.options.now ?? Date.now)();
		if (!isFreshLinearEvent(event, now)) {
			this.options.log(`gateway: refused ${id} for ${target}: webhookTimestamp is missing or more than a minute off`);
			return respond(response, 401);
		}

		if (this.spool.add({ id, target, source: "linear", receivedAt: now, signature, body: body.toString("base64") })) {
			this.options.log(`gateway: spooled ${id} for ${target}`);
			this.wakers.get(target)?.();
		}
		respond(response, 200);
	}

	/** Hands `target`'s events over, oldest first, until the gateway stops. */
	private async deliver(target: ProcessName): Promise<void> {
		const port = this.options.targets[target] as number;
		const retry = this.options.retry ?? DEFAULT_RETRY;
		const signal = this.stopping.signal;
		let backoff = retry.initialMs;

		while (!signal.aborted) {
			const event = this.spool.next(target);
			if (event === undefined) {
				await new Promise<void>((resolve) => this.wakers.set(target, resolve));
				continue;
			}

			const status = await handOver(event, port, signal);
			if (signal.aborted) {
				return;
			}
			if (status !== undefined && status >= 200 && status < 300) {
				this.spool.done(event.id);
				this.options.log(`gateway: ${target} accepted ${event.id}`);
				backoff = retry.initialMs;
				continue;
			}
			if (status !== undefined && PERMANENT.has(status)) {
				this.spool.rejected(event.id, status);
				this.options.log(`gateway: ${target} refused ${event.id} with ${status}; dropped it, check the webhook secrets`);
				continue;
			}

			this.options.log(
				`gateway: ${target} did not take ${event.id} (${status ?? "unreachable"}), retrying in ${backoff}ms`,
			);
			await sleep(backoff, undefined, { signal }).catch(() => {});
			backoff = Math.min(backoff * 2, retry.maxMs);
		}
	}
}

/** One hand-off attempt. Returns the status, or undefined when the process could not be reached. */
async function handOver(event: SpooledEvent, port: number, stopping: AbortSignal): Promise<number | undefined> {
	try {
		const response = await fetch(`http://127.0.0.1:${port}${HANDOFF_PATH}`, {
			method: "POST",
			headers: {
				"content-type": "application/octet-stream",
				[HEADERS.deliveryId]: event.id,
				[HEADERS.source]: event.source,
				[HEADERS.receivedAt]: String(event.receivedAt),
				[HEADERS.linearSignature]: event.signature,
			},
			body: Buffer.from(event.body, "base64"),
			signal: AbortSignal.any([stopping, AbortSignal.timeout(DELIVERY_TIMEOUT_MS)]),
		});
		await response.arrayBuffer();
		return response.status;
	} catch {
		return undefined;
	}
}

function respond(response: ServerResponse, status: number): void {
	response.writeHead(status, { "content-type": "text/plain" }).end();
}
