import type { IncomingMessage } from "node:http";

/**
 * The hand-off from the gateway to the process that owns an event: `POST /events` on that process's localhost port.
 *
 * The body is the sender's raw body and its signature header comes with it, so the owning process verifies the event
 * itself with its own copy of the webhook secret. A local process that can reach the port cannot forge an event, and
 * a compromised gateway can only pass on events the sender really signed.
 *
 * The owning process answers:
 * - `202` once the event is durably recorded, including when it had recorded it before
 * - `503` while it is starting or draining, so the gateway keeps the event and retries
 * - `400`, `401` or `413` when the event can never be accepted, so the gateway stops retrying it
 */
export const HANDOFF_PATH = "/events";

export const HEADERS = {
	deliveryId: "implementer-delivery-id",
	source: "implementer-source",
	receivedAt: "implementer-received-at",
	linearSignature: "linear-signature",
} as const;

/** Webhook bodies are small. Anything bigger is refused before it is read in full. */
export const MAX_BODY_BYTES = 1024 * 1024;

export class BodyTooLarge extends Error {}

/** Reads a request body, refusing more than `MAX_BODY_BYTES`. */
export async function readBody(request: IncomingMessage): Promise<Buffer> {
	const chunks: Buffer[] = [];
	let size = 0;
	for await (const chunk of request) {
		size += (chunk as Buffer).length;
		if (size > MAX_BODY_BYTES) {
			throw new BodyTooLarge();
		}
		chunks.push(chunk as Buffer);
	}
	return Buffer.concat(chunks);
}

/** A single-valued header, or undefined when it is absent or repeated. */
export function header(request: IncomingMessage, name: string): string | undefined {
	const value = request.headers[name];
	return typeof value === "string" ? value : undefined;
}
