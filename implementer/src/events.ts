import type { Context } from "@earendil-works/chord/context";
import { defineDocFamily, defineExtension, defineTask, type Harness } from "@earendil-works/pi-durable";
import type { Delivery } from "./inbox.ts";

/**
 * One record per delivery id, in the process's own database: the id of the task the delivery started.
 *
 * Pi Durable's `requestId` deduplicates submissions to a conversation, and a submission is model input. A webhook is
 * not model input, so implementer keys its own record on the delivery id instead. Reading the record and creating the task
 * happen in one commit, so the same delivery handed over twice, or by two racing requests, starts one task.
 */
const DeliveryRecord = defineDocFamily<{ taskId: number | null; receivedAt: number }, number>({
	kind: "implementer.delivery",
	version: 1,
	scope: "session",
	family: true,
	initial: (receivedAt) => ({ taskId: null, receivedAt }),
	checkpointWhen: () => true,
});

type EventInput = { readonly delivery: Delivery };
type EventState = { phase: "handle" };

/** What a process does with an event it has accepted. Runs inside a durable task, so it may run more than once. */
export type EventHandler = (delivery: EventInput["delivery"], context: Context) => Promise<void>;

/** The durable task that handles one accepted event. A restart that cuts it off runs `handle` again. */
function eventTask(handler: EventHandler) {
	return defineTask<EventInput, EventState, null>({
		name: "implementer.event",
		version: 1,
		initial: () => ({ phase: "handle" }),
		phases: {
			handle: async (task, runtime, context) => {
				await handler(task.input.delivery, context);
				await runtime.commit(() => ({ status: "terminal", outcome: { status: "completed", result: null } }), context);
			},
		},
		abort: (_task, runtime, context) =>
			runtime.commit(() => ({ status: "terminal", outcome: { status: "aborted" } }), context),
	});
}

/** The extension that carries a process's event task. Install it before the harness resumes. */
export function eventsExtension(handler: EventHandler) {
	const task = eventTask(handler);
	return { extension: defineExtension({ name: "implementer.events", tasks: [task] }), task };
}

/**
 * Durably records `delivery` and starts its task, unless that delivery was recorded before.
 *
 * Returns whether a task was started.
 */
export async function admit(
	harness: Harness,
	task: ReturnType<typeof eventTask>,
	delivery: Delivery,
	context: Context,
): Promise<boolean> {
	const root = await harness.root(context);
	return harness.commit(async (tx) => {
		const record = await tx.doc(DeliveryRecord, delivery.id, delivery.receivedAt);
		if (record.taskId !== null) {
			return false;
		}
		record.taskId = await tx.createTask(task, { delivery }, { ownership: { kind: "conversation" }, conversationId: root.id });
		return true;
	}, context);
}
