import { createHmac, timingSafeEqual } from "node:crypto";

/** How old a webhook may be when the gateway receives it. Linear recommends a minute, to guard against replays. */
export const LINEAR_FRESHNESS_MS = 60_000;

/**
 * Whether `signature`, the `Linear-Signature` header, is the hex HMAC-SHA256 of the raw body under `secret`.
 *
 * Compared in constant time. A missing or malformed header is simply not valid.
 */
export function verifyLinearSignature(body: Buffer, signature: string | undefined, secret: string): boolean {
	if (signature === undefined || !/^[0-9a-f]{64}$/i.test(signature)) {
		return false;
	}
	const expected = createHmac("sha256", secret).update(body).digest();
	return timingSafeEqual(expected, Buffer.from(signature, "hex"));
}

/** The signing half of a test: what Linear would put in `Linear-Signature`. */
export function signLinear(body: Buffer | string, secret: string): string {
	return createHmac("sha256", secret).update(body).digest("hex");
}

/**
 * Whether the signed `webhookTimestamp` in the body is within `LINEAR_FRESHNESS_MS` of `now`.
 *
 * The timestamp is inside the signed body, so it is checked only after the signature. The `Linear-Timestamp` header
 * is not signed and is ignored.
 */
export function isFreshLinearEvent(event: unknown, now: number): boolean {
	if (typeof event !== "object" || event === null) {
		return false;
	}
	const sent = (event as { webhookTimestamp?: unknown }).webhookTimestamp;
	return typeof sent === "number" && Math.abs(now - sent) <= LINEAR_FRESHNESS_MS;
}
