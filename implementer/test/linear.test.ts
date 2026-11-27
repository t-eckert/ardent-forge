import { describe, expect, it } from "vitest";
import { isFreshLinearEvent, signLinear, verifyLinearSignature } from "../src/linear.ts";

describe("verifyLinearSignature", () => {
	const body = Buffer.from('{"type":"AgentSessionEvent"}');

	it("accepts the HMAC of the body under the secret", () => {
		expect(verifyLinearSignature(body, signLinear(body, "s3cret"), "s3cret")).toBe(true);
	});

	it("refuses another secret, another body, and a missing or malformed header", () => {
		expect(verifyLinearSignature(body, signLinear(body, "other"), "s3cret")).toBe(false);
		expect(verifyLinearSignature(Buffer.from("{}"), signLinear(body, "s3cret"), "s3cret")).toBe(false);
		expect(verifyLinearSignature(body, undefined, "s3cret")).toBe(false);
		expect(verifyLinearSignature(body, "abc", "s3cret")).toBe(false);
	});
});

describe("isFreshLinearEvent", () => {
	it("takes a webhookTimestamp within a minute either way", () => {
		expect(isFreshLinearEvent({ webhookTimestamp: 1_000_000 }, 1_000_000 + 60_000)).toBe(true);
		expect(isFreshLinearEvent({ webhookTimestamp: 1_000_000 }, 1_000_000 - 60_000)).toBe(true);
	});

	it("refuses an old, missing or non-numeric one", () => {
		expect(isFreshLinearEvent({ webhookTimestamp: 1_000_000 }, 1_000_000 + 60_001)).toBe(false);
		expect(isFreshLinearEvent({}, 0)).toBe(false);
		expect(isFreshLinearEvent({ webhookTimestamp: "0" }, 0)).toBe(false);
		expect(isFreshLinearEvent(null, 0)).toBe(false);
	});
});
