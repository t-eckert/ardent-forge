#!/usr/bin/env -S node --disable-warning=ExperimentalWarning
import { join } from "node:path";
import { parseArgs } from "node:util";
import { Containers } from "./containers.ts";
import { LockHeldError } from "./lock.ts";
import { probeFence } from "./probe.ts";
import { DEFAULT_PORTS, PROCESSES, type ProcessName, parseProcessName, processPaths, UsageError } from "./processes.ts";
import { runProcess } from "./run.ts";
import { snapshotLocal } from "./snapshot.ts";

const USAGE = `usage:
  implementer run <process> [--state-dir DIR] [--grace SECONDS]
  implementer backup --local <process> [--state-dir DIR] [--keep N]
  implementer probe [--state-dir DIR]     check the session container's network fence; exits 1 if it does not hold

processes: gateway, implementer

environment:
  IMPLEMENTER_STATE_DIR                  default for --state-dir
  IMPLEMENTER_<PROCESS>_PORT             a process's localhost port (gateway 7410, implementer 7411)
  LINEAR_WEBHOOK_SECRET_<PROCESS> the signing secret of the Linear webhook for that process
  IMPLEMENTER_SESSION_IMAGE              the session container image (default localhost/implementer-session:latest)
  IMPLEMENTER_PROXY                      the implementer's crucible proxy, such as http://127.0.0.1:3128
  IMPLEMENTER_PODMAN_CGROUPS             split (default; needs a unit with Delegate=yes) or enabled, for a shell`;

const DEFAULT_STATE_DIR = "/data/implementer";
/** How long `harness.close()` gets after the grace period. See docs/design.md, "Two backstops". */
const CLOSE_DEADLINE_MS = 15_000;

async function main(argv: string[]): Promise<number> {
	const { values, positionals } = parseArgs({
		args: argv,
		allowPositionals: true,
		options: {
			"state-dir": { type: "string", default: process.env.IMPLEMENTER_STATE_DIR ?? DEFAULT_STATE_DIR },
			grace: { type: "string", default: "30" },
			local: { type: "boolean", default: false },
			keep: { type: "string", default: "5" },
			help: { type: "boolean", short: "h", default: false },
		},
	});
	const [command, target] = positionals;
	if (values.help || command === undefined) {
		console.log(USAGE);
		return values.help ? 0 : 2;
	}
	const stateDir = values["state-dir"];

	switch (command) {
		case "run":
			return runProcess({
				name: parseProcessName(target),
				stateDir,
				graceMs: seconds(values.grace, "--grace") * 1000,
				closeDeadlineMs: CLOSE_DEADLINE_MS,
				shutdown: shutdownSignal(),
				log: (message) => console.error(message),
				ports: ports(process.env),
				linearSecrets: linearSecrets(process.env),
				...(target === "implementer" ? { containers: containers(stateDir, process.env) } : {}),
			});
		case "probe": {
			const paths = processPaths(stateDir, "implementer");
			const result = await probeFence(containers(stateDir, process.env), {
				image: sessionImage(process.env),
				worktree: join(paths.dir, "probe"),
				outputPath: join(paths.dir, "probe.log"),
			});
			console.error(result.report);
			console.error(result.passed ? "the fence holds" : "the fence does NOT hold");
			return result.passed ? 0 : 1;
		}
		case "backup": {
			if (!values.local) {
				throw new UsageError("only `implementer backup --local <process>` exists so far; shipping snapshots off the box is the Forge's job");
			}
			const name = parseProcessName(target);
			const paths = processPaths(stateDir, name);
			const result = snapshotLocal({ database: paths.database, snapshots: paths.snapshots, keep: count(values.keep, "--keep") });
			if (result.kind === "skipped") {
				console.error(`${name}: snapshot skipped, ${result.reason}`);
			} else {
				console.error(`${name}: snapshot written to ${result.path}, pruned ${result.pruned.length}`);
			}
			return 0;
		}
		default:
			throw new UsageError(`unknown command ${command}`);
	}
}

/** Settles on the first SIGTERM or SIGINT. A second signal exits at once, for a person who does not want to wait. */
function shutdownSignal(): Promise<void> {
	return new Promise((resolve) => {
		let received = false;
		const onSignal = (signal: NodeJS.Signals) => {
			if (received) {
				console.error(`${signal} again, exiting now`);
				process.exit(130);
			}
			received = true;
			resolve();
		};
		process.on("SIGTERM", onSignal);
		process.on("SIGINT", onSignal);
	});
}

/** The implementer's Podman runner, with its shared build cache under its state directory. */
function containers(stateDir: string, env: NodeJS.ProcessEnv): Containers {
	const cgroups = env.IMPLEMENTER_PODMAN_CGROUPS ?? "split";
	if (cgroups !== "split" && cgroups !== "enabled") {
		throw new UsageError(`IMPLEMENTER_PODMAN_CGROUPS must be split or enabled, got ${cgroups}`);
	}
	return new Containers({
		process: "implementer",
		cacheDir: join(processPaths(stateDir, "implementer").dir, "cache"),
		proxy: env.IMPLEMENTER_PROXY,
		cgroups,
		log: (message) => console.error(message),
	});
}

function sessionImage(env: NodeJS.ProcessEnv): string {
	return env.IMPLEMENTER_SESSION_IMAGE ?? "localhost/implementer-session:latest";
}

/** Each process's localhost port: `IMPLEMENTER_<PROCESS>_PORT`, or its default. */
function ports(env: NodeJS.ProcessEnv): Record<ProcessName, number> {
	return Object.fromEntries(
		PROCESSES.map((p) => {
			const value = env[`IMPLEMENTER_${p.toUpperCase()}_PORT`];
			if (value === undefined) {
				return [p, DEFAULT_PORTS[p]];
			}
			const port = Number(value);
			if (!Number.isInteger(port) || port < 1 || port > 65535) {
				throw new UsageError(`IMPLEMENTER_${p.toUpperCase()}_PORT must be a port number, got ${value}`);
			}
			return [p, port];
		}),
	) as Record<ProcessName, number>;
}

/**
 * Linear webhook secrets: `LINEAR_WEBHOOK_SECRET_<PROCESS>`. The gateway's environment holds every one it routes, and a
 * job's holds only its own, under the same name.
 */
function linearSecrets(env: NodeJS.ProcessEnv): Partial<Record<ProcessName, string>> {
	const secrets: Partial<Record<ProcessName, string>> = {};
	for (const p of PROCESSES) {
		const value = env[`LINEAR_WEBHOOK_SECRET_${p.toUpperCase()}`];
		if (value !== undefined && value !== "") {
			secrets[p] = value;
		}
	}
	return secrets;
}

function seconds(value: string, flag: string): number {
	const n = Number(value);
	if (!Number.isFinite(n) || n < 0) {
		throw new UsageError(`${flag} takes a number of seconds, got ${value}`);
	}
	return n;
}

function count(value: string, flag: string): number {
	const n = Number(value);
	if (!Number.isInteger(n) || n < 1) {
		throw new UsageError(`${flag} takes a whole number of at least 1, got ${value}`);
	}
	return n;
}

main(process.argv.slice(2)).then(
	(code) => process.exit(code),
	(error: unknown) => {
		if (error instanceof UsageError) {
			console.error(`${error.message}\n\n${USAGE}`);
			process.exit(2);
		}
		if (error instanceof LockHeldError) {
			console.error(error.message);
			process.exit(75);
		}
		console.error(error);
		process.exit(1);
	},
);
