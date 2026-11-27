import { mkdirSync } from "node:fs";
import type { Containers } from "./containers.ts";

/**
 * The fence probe, run from inside a session container. See docs/design.md, "Isolating a session".
 *
 * It passes only if the container can reach an allowed host through the proxy, cannot reach a host the proxy does not
 * allow, and cannot reach anything by going around the proxy. Outside the fence the last two fail, which is the point:
 * a probe that passed everywhere would prove nothing.
 */
const SCRIPT = `
set -u
fail=0
reach() { curl --silent --show-error --output /dev/null --max-time 15 "$@"; }
if reach https://api.anthropic.com/; then echo "ok: api.anthropic.com is reachable through the proxy"
else echo "FAIL: api.anthropic.com is not reachable"; fail=1; fi
if reach https://api.stripe.com/; then echo "FAIL: api.stripe.com is reachable"; fail=1
else echo "ok: api.stripe.com is refused"; fi
if reach --noproxy '*' https://api.anthropic.com/; then echo "FAIL: going around the proxy works"; fail=1
else echo "ok: going around the proxy is refused"; fi
exit $fail
`;

export type ProbeResult = { readonly passed: boolean; readonly report: string };

export async function probeFence(
	containers: Containers,
	options: { readonly image: string; readonly worktree: string; readonly outputPath: string },
): Promise<ProbeResult> {
	mkdirSync(options.worktree, { recursive: true });
	const result = await containers.run({
		runId: `probe-${Date.now()}`,
		image: options.image,
		worktree: options.worktree,
		command: ["sh", "-c", SCRIPT],
		outputPath: options.outputPath,
	});
	return { passed: result.exitCode === 0, report: result.tail.trim() };
}
