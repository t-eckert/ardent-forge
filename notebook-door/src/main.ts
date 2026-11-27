// The Notebook door: `node src/main.ts`. See README.md.
import { readFileSync } from "node:fs";
import { checkConfig, type DoorConfig } from "./grants.ts";
import { Notebook } from "./notebook.ts";
import { startServer } from "./server.ts";

const env = process.env;
const configPath = env.NOTEBOOK_DOOR_CONFIG ?? "/etc/ardent-forge/notebook-door.json";
const config = JSON.parse(readFileSync(configPath, "utf8")) as DoorConfig;
checkConfig(config);

// Each grant is keyed by the environment variable holding its caller's token. A grant whose token is not set has no
// caller, so a token that was never issued opens nothing.
const callers = Object.entries(config.grants).flatMap(([variable, grant]) => {
	const token = env[variable];
	return token === undefined || token.length < 32 ? [] : [{ token, grant }];
});

const log = (message: string) => console.log(message);
const syncshot = env.SYNCSHOT;
if (syncshot === undefined) {
	throw new Error("SYNCSHOT must name syncshot.py");
}
const notebook = new Notebook({ config, syncshot, scratch: env.NOTEBOOK_DOOR_SCRATCH ?? "/data/ardent-forge/notebook-door", log });
const port = Number(env.NOTEBOOK_DOOR_PORT ?? "8095");
await startServer({ host: "127.0.0.1", port, notebook, callers, log });
log(`notebook-door: listening on 127.0.0.1:${port} for ${callers.map((c) => c.grant.caller).join(", ") || "no callers"}`);
