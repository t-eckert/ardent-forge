import { mkdtempSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { HANDOFF_PATH, HEADERS } from "../src/handoff.ts";
import type { Delivery } from "../src/inbox.ts";
import { signLinear } from "../src/linear.ts";
import { type ProcessName, processPaths } from "../src/processes.ts";
import { runProcess } from "../src/run.ts";
import { Spool } from "../src/spool.ts";

const SECRET = "linear-implementer-secret";

/** A free localhost port, so the gateway knows where the implementer will listen before it starts. */
async function freePort(): Promise<number> {
	const server = createServer();
	await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
	const { port } = server.address() as { port: number };
	await new Promise<void>((resolve) => server.close(() => resolve()));
	return port;
}

async function waitFor(check: () => boolean, ms = 5000): Promise<void> {
	const until = Date.now() + ms;
	while (!check()) {
		if (Date.now() > until) {
			throw new Error("timed out waiting");
		}
		await new Promise((r) => setTimeout(r, 20));
	}
}

type Running = { readonly port: number; readonly stop: () => Promise<number> };
const running: Running[] = [];

afterEach(async () => {
	await Promise.all(running.splice(0).map((r) => r.stop()));
});

async function start(
	name: ProcessName,
	stateDir: string,
	ports: Record<ProcessName, number>,
	options: { onEvent?: (delivery: Delivery) => void; logs?: string[] } = {},
): Promise<Running> {
	let shutdown!: () => void;
	let ready!: (port: number) => void;
	const listening = new Promise<number>((resolve) => {
		ready = resolve;
	});
	const exit = runProcess({
		name,
		stateDir,
		graceMs: 2000,
		closeDeadlineMs: 5000,
		shutdown: new Promise<void>((resolve) => {
			shutdown = resolve;
		}),
		log: (m) => options.logs?.push(m),
		ports,
		linearSecrets: { implementer: SECRET },
		handoffRetry: { initialMs: 20, maxMs: 100 },
		onReady: ready,
		...(options.onEvent === undefined ? {} : { onEvent: async (d: Delivery) => options.onEvent?.(d) }),
	});
	const port = await Promise.race([listening, exit.then((code) => Promise.reject(new Error(`exited ${code}`)))]);
	let stopped: Promise<number> | undefined;
	const handle = {
		port,
		stop: () => {
			if (stopped === undefined) {
				shutdown();
				stopped = exit;
			}
			return stopped;
		},
	};
	running.push(handle);
	return handle;
}

function agentSessionEvent(at = Date.now()): string {
	return JSON.stringify({ type: "AgentSessionEvent", action: "created", webhookTimestamp: at, data: {} });
}

async function webhook(port: number, body: string, options: { id?: string; signature?: string } = {}) {
	return fetch(`http://127.0.0.1:${port}/linear/implementer`, {
		method: "POST",
		headers: {
			"content-type": "application/json",
			"linear-delivery": options.id ?? crypto.randomUUID(),
			"linear-signature": options.signature ?? signLinear(body, SECRET),
		},
		body,
	});
}

async function scene() {
	const stateDir = mkdtempSync(join(tmpdir(), "implementer-gateway-"));
	const ports = { gateway: 0, implementer: await freePort() };
	return { stateDir, ports };
}

describe("the gateway and the hand-off", () => {
	it("delivers a delegated issue's event to the implementer", async () => {
		const { stateDir, ports } = await scene();
		const handled: Delivery[] = [];
		await start("implementer", stateDir, ports, { onEvent: (d) => handled.push(d) });
		const gateway = await start("gateway", stateDir, ports);

		const response = await webhook(gateway.port, agentSessionEvent(), { id: "delivery-1" });
		expect(response.status).toBe(200);

		await waitFor(() => handled.length === 1);
		expect(handled[0]?.id).toBe("delivery-1");
		expect(handled[0]?.event).toMatchObject({ type: "AgentSessionEvent", action: "created" });
	});

	it("refuses a bad signature and a stale timestamp, and spools neither", async () => {
		const { stateDir, ports } = await scene();
		const gateway = await start("gateway", stateDir, ports);

		const body = agentSessionEvent();
		expect((await webhook(gateway.port, body, { signature: signLinear(body, "wrong") })).status).toBe(401);
		expect((await webhook(gateway.port, body, { signature: "not-hex" })).status).toBe(401);
		expect((await webhook(gateway.port, agentSessionEvent(Date.now() - 5 * 60_000))).status).toBe(401);

		expect(await gateway.stop()).toBe(0);
		const spool = Spool.open(processPaths(stateDir, "gateway").spool);
		expect(spool.list()).toEqual([]);
		spool.close();
	});

	it("has no route for a process it holds no secret for", async () => {
		const { stateDir, ports } = await scene();
		const gateway = await start("gateway", stateDir, ports);
		const body = agentSessionEvent();
		const response = await fetch(`http://127.0.0.1:${gateway.port}/linear/gateway`, {
			method: "POST",
			headers: { "linear-delivery": "x", "linear-signature": signLinear(body, SECRET) },
			body,
		});
		expect(response.status).toBe(404);
	});

	it("keeps events in the spool while the implementer is down, and delivers them once it starts", async () => {
		const { stateDir, ports } = await scene();
		const gateway = await start("gateway", stateDir, ports);

		expect((await webhook(gateway.port, agentSessionEvent(), { id: "early-1" })).status).toBe(200);
		expect((await webhook(gateway.port, agentSessionEvent(), { id: "early-2" })).status).toBe(200);

		// Restarting the gateway too shows the spool is on disk, not in memory.
		await gateway.stop();
		const spool = Spool.open(processPaths(stateDir, "gateway").spool);
		expect(spool.list().map((e) => e.id)).toEqual(["early-1", "early-2"]);
		spool.close();
		await start("gateway", stateDir, ports);

		const handled: string[] = [];
		await start("implementer", stateDir, ports, { onEvent: (d) => handled.push(d.id) });
		await waitFor(() => handled.length === 2);
		expect(handled).toEqual(["early-1", "early-2"]);
	});

	it("starts one run for an event delivered twice, even across a restart", async () => {
		const { stateDir, ports } = await scene();
		const handled: string[] = [];
		const onEvent = (d: Delivery) => handled.push(d.id);
		const logs: string[] = [];
		let implementer = await start("implementer", stateDir, ports, { onEvent, logs });

		const body = agentSessionEvent();
		const handOver = (port: number) =>
			fetch(`http://127.0.0.1:${port}${HANDOFF_PATH}`, {
				method: "POST",
				headers: {
					[HEADERS.deliveryId]: "twice",
					[HEADERS.source]: "linear",
					[HEADERS.receivedAt]: String(Date.now()),
					[HEADERS.linearSignature]: signLinear(body, SECRET),
				},
				body,
			});

		const [first, second] = await Promise.all([handOver(implementer.port), handOver(implementer.port)]);
		expect([first.status, second.status]).toEqual([202, 202]);
		await waitFor(() => handled.length === 1);

		await implementer.stop();
		implementer = await start("implementer", stateDir, ports, { onEvent, logs });
		expect((await handOver(implementer.port)).status).toBe(202);
		await new Promise((r) => setTimeout(r, 200));

		expect(handled).toEqual(["twice"]);
		expect(logs.filter((l) => l.includes("already had twice"))).toHaveLength(2);
	});

	it("has the implementer check the signature again, so a local process cannot forge an event", async () => {
		const { stateDir, ports } = await scene();
		const handled: string[] = [];
		const implementer = await start("implementer", stateDir, ports, { onEvent: (d) => handled.push(d.id) });
		const body = agentSessionEvent();
		const response = await fetch(`http://127.0.0.1:${implementer.port}${HANDOFF_PATH}`, {
			method: "POST",
			headers: {
				[HEADERS.deliveryId]: "forged",
				[HEADERS.source]: "linear",
				[HEADERS.receivedAt]: "0",
				[HEADERS.linearSignature]: signLinear(body, "guessed"),
			},
			body,
		});
		expect(response.status).toBe(401);
		await new Promise((r) => setTimeout(r, 100));
		expect(handled).toEqual([]);
	});

	it("answers 503 while draining, so the gateway keeps the event", async () => {
		const { stateDir, ports } = await scene();
		const implementer = await start("implementer", stateDir, ports);
		const stopping = implementer.stop();
		// The inbox drains on the shutdown signal, before the harness closes.
		await new Promise((r) => setTimeout(r, 10));
		const body = agentSessionEvent();
		const response = await fetch(`http://127.0.0.1:${implementer.port}${HANDOFF_PATH}`, {
			method: "POST",
			headers: {
				[HEADERS.deliveryId]: "late",
				[HEADERS.source]: "linear",
				[HEADERS.receivedAt]: "0",
				[HEADERS.linearSignature]: signLinear(body, SECRET),
			},
			body,
		}).catch(() => undefined);
		// Either the drain answered 503, or the listener had already closed: both leave the event with the gateway.
		expect(response === undefined || response.status === 503).toBe(true);
		expect(await stopping).toBe(0);
	});
});
