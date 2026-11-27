import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { containerName, Containers } from "../src/containers.ts";

function scratch() {
	const dir = mkdtempSync(join(tmpdir(), "implementer-containers-"));
	return { dir, worktree: dir, cacheDir: join(dir, "cache") };
}

describe("Containers.args", () => {
	const { worktree, cacheDir } = scratch();
	const containers = new Containers({
		process: "implementer",
		cacheDir,
		proxy: "http://127.0.0.1:3128",
		log: () => {},
	});
	const args = containers.args({
		runId: "GAL-1/run 2",
		image: "localhost/implementer-session:latest",
		worktree,
		command: ["cargo", "check"],
		env: { EXTRA: "1" },
		outputPath: "/dev/null",
	});

	it("shares the host network, stays in the unit's cgroup, and drops privileges", () => {
		expect(args).toContain("--network=host");
		expect(args).toContain("--cgroups=split");
		expect(args).toContain("--userns=keep-id");
		expect(args).toContain("--cap-drop=all");
		expect(args).toContain("--security-opt=no-new-privileges");
	});

	it("mounts only the worktree and the cache", () => {
		const volumes = args.flatMap((a, i) => (a === "--volume" ? [args[i + 1]] : []));
		expect(volumes).toEqual([`${worktree}:/work`, `${cacheDir}:/cache`]);
	});

	it("labels the container with its process and run id, under a safe name", () => {
		expect(args).toContain("implementer.process=implementer");
		expect(args).toContain("implementer.run-id=GAL-1/run 2");
		expect(args[args.indexOf("--name") + 1]).toBe("implementer-GAL-1-run-2");
	});

	it("points both spellings of the proxy variables at the proxy, and keeps the caller's env", () => {
		for (const name of ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]) {
			expect(args).toContain(`${name}=http://127.0.0.1:3128`);
		}
		expect(args).toContain("CARGO_TARGET_DIR=/cache/target");
		expect(args).toContain("EXTRA=1");
		expect(args.slice(-3)).toEqual(["localhost/implementer-session:latest", "cargo", "check"]);
	});
});

const IMAGE = process.env.IMPLEMENTER_TEST_IMAGE ?? "localhost/implementer-session:latest";
const hasImage = spawnSync("podman", ["image", "exists", IMAGE]).status === 0;

/** Real Podman. Runs where the session image has been built; skipped elsewhere, such as CI. */
describe.skipIf(!hasImage)("Containers with Podman", () => {
	function runner(dir: string) {
		return new Containers({ process: "implementer", cacheDir: join(dir, "cache"), cgroups: "enabled", log: () => {} });
	}

	it("runs a command in the worktree and returns its exit code and output", async () => {
		const { dir, worktree } = scratch();
		const outputPath = join(dir, "out.log");
		const result = await runner(dir).run({
			runId: `t-${Date.now()}`,
			image: IMAGE,
			worktree,
			command: ["sh", "-c", "pwd; touch /work/made-here; echo to-stderr >&2; exit 3"],
			outputPath,
		});
		expect(result.exitCode).toBe(3);
		expect(result.tail).toContain("/work");
		expect(readFileSync(outputPath, "utf8")).toContain("to-stderr");
		expect(spawnSync("test", ["-f", join(worktree, "made-here")]).status).toBe(0);
	}, 60_000);

	it("stops the container when the run is aborted", async () => {
		const { dir, worktree } = scratch();
		const runId = `t-abort-${Date.now()}`;
		const controller = new AbortController();
		const started = Date.now();
		const run = runner(dir).run(
			{ runId, image: IMAGE, worktree, command: ["sleep", "300"], outputPath: join(dir, "out.log") },
			controller.signal,
		);
		setTimeout(() => controller.abort(), 2000);
		const result = await run;
		expect(result.exitCode).toBeUndefined();
		expect(Date.now() - started).toBeLessThan(30_000);
		expect(spawnSync("podman", ["container", "exists", containerName(runId)]).status).not.toBe(0);
	}, 60_000);

	it("runs one container at a time", async () => {
		const { dir, worktree } = scratch();
		const containers = runner(dir);
		const log = join(worktree, "order");
		const step = (name: string) =>
			containers.run({
				runId: `t-${name}-${Date.now()}`,
				image: IMAGE,
				worktree,
				command: ["sh", "-c", `echo start-${name} >> /work/order; sleep 1; echo end-${name} >> /work/order`],
				outputPath: join(dir, `${name}.log`),
			});
		await Promise.all([step("a"), step("b")]);
		expect(readFileSync(log, "utf8").trim().split("\n")).toEqual(["start-a", "end-a", "start-b", "end-b"]);
	}, 60_000);

	it("removes a container a crashed implementer left behind", async () => {
		const { dir } = scratch();
		const runId = `t-orphan-${Date.now()}`;
		const name = containerName(runId);
		const started = spawnSync("podman", [
			"run", "--detach", "--name", name,
			"--label", "implementer.process=implementer", "--label", `implementer.run-id=${runId}`,
			IMAGE, "sleep", "300",
		]);
		expect(started.status).toBe(0);

		const removed = await runner(dir).reap();
		expect(removed).toContain(name);
		expect(spawnSync("podman", ["container", "exists", name]).status).not.toBe(0);
	}, 60_000);
});
