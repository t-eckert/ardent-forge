import { mkdirSync } from "node:fs";
import { setTimeout as sleep } from "node:timers/promises";
import { BACKGROUND_CONTEXT } from "@earendil-works/chord/context";
import { createModels } from "@earendil-works/pi-ai/models";
import { anthropicProvider } from "@earendil-works/pi-ai/providers/anthropic";
import { createRegistry, type Extension, Harness } from "@earendil-works/pi-durable";
import { openNodeSqliteStorage } from "@earendil-works/pi-durable/storage/sqlite/node";
import type { Containers } from "./containers.ts";
import { admit, type EventHandler, eventsExtension } from "./events.ts";
import { Gateway } from "./gateway.ts";
import { Inbox } from "./inbox.ts";
import { ProcessLock } from "./lock.ts";
import { hasHarness, PROCESSES, type ProcessName, processPaths } from "./processes.ts";

export type Log = (message: string) => void;

export type RunOptions = {
	readonly name: ProcessName;
	readonly stateDir: string;
	/** How long in-flight work gets to reach a checkpoint after a shutdown signal. */
	readonly graceMs: number;
	/** How long `harness.close()` gets after the grace period, before the process gives up and exits non-zero. */
	readonly closeDeadlineMs: number;
	/** Settles when the process should drain and exit: the first SIGTERM or SIGINT. */
	readonly shutdown: Promise<void>;
	readonly log: Log;
	/** Every process's localhost port: the gateway listens on its own, and hands events to the others on theirs. */
	readonly ports: Readonly<Record<ProcessName, number>>;
	/**
	 * Linear webhook signing secrets by owning process. The gateway needs every one it routes; a job needs only its own,
	 * to check events again when they are handed over.
	 */
	readonly linearSecrets: Partial<Record<ProcessName, string>>;
	/** What the job does with an accepted event. Until a job has real work, it logs the event. */
	readonly onEvent?: EventHandler;
	/** The implementer's containers. Any left by a crashed run are removed before the harness resumes. */
	readonly containers?: Containers;
	/** The gateway's wait between hand-off attempts. Tests shorten it. */
	readonly handoffRetry?: { readonly initialMs: number; readonly maxMs: number };
	/** Called once the process is ready to take work, with the port it actually listens on. */
	readonly onReady?: (port: number) => void;
};

/**
 * `implementer run <process>`: take the process's lock, then run the gateway, or open the job's harness and take the events
 * the gateway hands over, until told to stop.
 *
 * The exit follows docs/design.md, "Graceful exit, with a timeout": let in-flight work reach a checkpoint within the
 * grace period, then `harness.close()`. A clean close is not counted toward Pi Durable's restart limit, and a SIGKILL
 * is, which is why implementer ends itself rather than leaving it to systemd.
 *
 * Returns the exit code: 0 for a clean exit, 1 when the close deadline passed.
 */
export async function runProcess(options: RunOptions): Promise<number> {
	const paths = processPaths(options.stateDir, options.name);
	mkdirSync(paths.dir, { recursive: true });
	const lock = ProcessLock.acquire(paths.lock);
	try {
		if (!hasHarness(options.name)) {
			return await runGateway(options, paths.spool);
		}
		return await runJob(options, paths.database);
	} finally {
		lock.release();
	}
}

async function runGateway(options: RunOptions, spoolPath: string): Promise<number> {
	const gateway = await Gateway.start({
		spoolPath,
		port: options.ports.gateway,
		targets: Object.fromEntries(PROCESSES.filter((p) => p !== "gateway").map((p) => [p, options.ports[p]])),
		linearSecrets: options.linearSecrets,
		log: options.log,
		...(options.handoffRetry === undefined ? {} : { retry: options.handoffRetry }),
	});
	options.onReady?.(gateway.port);
	await untilShutdown(options.shutdown);
	options.log(`gateway: draining, up to ${options.graceMs}ms for in-flight requests`);
	// Whatever is still in the spool stays there for the next start. Only requests in flight need the grace period.
	const stopped = await Promise.race([gateway.stop().then(() => true), sleep(options.graceMs).then(() => false)]);
	if (!stopped) {
		options.log("gateway: requests still in flight after the grace period, exiting anyway");
		return 1;
	}
	options.log("gateway: closed cleanly");
	return 0;
}

async function runJob(options: RunOptions, database: string): Promise<number> {
	const context = BACKGROUND_CONTEXT;
	const onEvent = options.onEvent ?? logEvent(options.name, options.log);
	const events = eventsExtension(onEvent);
	const harness = await openHarness(database, events.extension, options.log);

	// Listening starts before the harness resumes, but the inbox answers 503 until `open()`, so the gateway waits.
	const inbox = await Inbox.start({
		port: options.ports[options.name],
		linearSecret: options.linearSecrets[options.name],
		accept: async (delivery) => {
			const started = await admit(harness, events.task, delivery, context);
			options.log(`${options.name}: ${started ? "accepted" : "already had"} ${delivery.id}`);
		},
		log: (message) => options.log(`${options.name} ${message}`),
	}).catch(async (error: unknown) => {
		await harness.close(context);
		throw error;
	});
	try {
		await options.containers?.reap();
		harness.resume();
		inbox.open();
		options.log(`${options.name}: running, taking events on 127.0.0.1:${inbox.port}`);
		options.onReady?.(inbox.port);

		await untilShutdown(options.shutdown);
		// Step 1 of the graceful exit: stop taking new work. The gateway keeps new events in its spool.
		inbox.drain();
		options.log(`${options.name}: draining, up to ${options.graceMs}ms for in-flight work`);

		const idle = await Promise.race([
			harness.waitForIdle(context).then(() => true),
			sleep(options.graceMs).then(() => false),
		]);
		if (!idle) {
			options.log(`${options.name}: grace period over, aborting what is still running`);
		}

		const closed = await Promise.race([
			harness.close(context).then(() => true),
			sleep(options.closeDeadlineMs).then(() => false),
		]);
		if (!closed) {
			options.log(`${options.name}: close did not finish within ${options.closeDeadlineMs}ms, exiting anyway`);
			return 1;
		}
		options.log(`${options.name}: closed cleanly`);
		return 0;
	} finally {
		await inbox.stop();
	}
}

/** Resolves on shutdown, keeping the process alive until then. */
async function untilShutdown(shutdown: Promise<void>): Promise<void> {
	// Signal listeners do not keep Node's event loop alive, and an idle harness may hold no timers, so without this
	// the process would exit on its own the moment it had nothing scheduled.
	const keepAlive = setInterval(() => {}, 2 ** 30);
	try {
		await shutdown;
	} finally {
		clearInterval(keepAlive);
	}
}

/** The stand-in handler until a job has real work: say what arrived. */
function logEvent(name: ProcessName, log: Log): EventHandler {
	return async (delivery) => {
		const { type, action } = delivery.event;
		log(`${name}: handling ${delivery.source} ${String(type)} ${String(action)} from ${delivery.id}`);
	};
}

async function openHarness(database: string, events: Extension, log: Log): Promise<Harness> {
	const models = createModels();
	models.setProvider(anthropicProvider());
	const registry = createRegistry();
	// Installed before the harness opens, so pending event tasks from the last run find their definition.
	registry.install(events);
	const storage = await openNodeSqliteStorage(database);
	return Harness.open(
		storage,
		{
			models,
			registry,
			onReport: (error, info) => log(`pi-durable ${info.type}: ${error instanceof Error ? error.message : String(error)}`),
		},
		BACKGROUND_CONTEXT,
	);
}
