/**
 * Typed API client — every response parses through a zod schema.
 *
 * Three promises this layer keeps:
 *  1. Each return type is a real schema-validated object (not `unknown`/`any`).
 *  2. Backend contract drift fails loudly at the parse boundary, not silently
 *     in a view. The error includes endpoint + field path.
 *  3. Fetches respect VITE_API_URL (absolute) or fall back to relative paths
 *     (same-origin — works with the vite proxy in hybrid dev, or the Caddy-
 *     fronted static bundle in production).
 */

import { z, type ZodType } from 'zod';
import { Task } from '$lib/schemas/task';

const API_BASE: string = (import.meta.env?.VITE_API_URL ?? '').replace(/\/$/, '');

class ApiError extends Error {
	constructor(
		public status: number,
		public endpoint: string,
		message: string
	) {
		super(`${endpoint} → ${status}: ${message}`);
	}
}

async function request<T>(path: string, schema: ZodType<T>, init?: RequestInit): Promise<T> {
	const url = `${API_BASE}${path}`;
	const res = await fetch(url, {
		headers: { 'Content-Type': 'application/json' },
		...init
	});
	if (!res.ok) {
		const text = await res.text().catch(() => '(no body)');
		throw new ApiError(res.status, path, text);
	}
	const json = await res.json();
	const parsed = schema.safeParse(json);
	if (!parsed.success) {
		const pretty = parsed.error.issues
			.map((i) => `${i.path.join('.') || '<root>'}: ${i.message}`)
			.join(' · ');
		throw new ApiError(res.status, path, `parse failed — ${pretty}`);
	}
	return parsed.data;
}

// ─── schemas per endpoint ────────────────────────────────────────────────────

const ConnectorTool = z.object({
	name: z.string(),
	description: z.string(),
	long_running: z.boolean()
});
const Connector = z.object({ name: z.string(), tools: z.array(ConnectorTool) });
const ConnectorList = z.array(Connector);
const HealthMap = z.record(z.string(), z.boolean());

const AgentRoster = z.object({
	name: z.string(),
	task_type: z.string(),
	stages: z.array(z.string()),
	connectors: z.array(z.string())
});
const AgentList = z.array(AgentRoster);

const MemoryEntry = z.object({
	filename: z.string(),
	slug: z.string(),
	name: z.string(),
	description: z.string(),
	type: z.enum(['user', 'feedback', 'project', 'reference']),
	body: z.string(),
	updated_at: z.string().nullable().optional()
});
const MemoryList = z.array(MemoryEntry);

const WeatherCurrent = z.object({
	location: z.string(),
	currentC: z.number(),
	summary: z.string(),
	daily: z.array(z.object({
		date: z.string(),
		min_c: z.number(),
		max_c: z.number(),
		precipitation_mm: z.number(),
		description: z.string()
	})).optional()
});

const Repo = z.object({
	name: z.string(),
	path: z.string(),
	default_branch: z.string()
});
const RepoList = z.array(Repo);
export type Repo = z.infer<typeof Repo>;

const Project = z.object({
	name: z.string(),
	path: z.string(),
	repos: z.array(Repo)
});
const ProjectList = z.array(Project);
export type Project = z.infer<typeof Project>;

const Schedule = z.object({
	id: z.string(),
	name: z.string(),
	cron_expr: z.string(),
	task_type: z.string(),
	enabled: z.boolean(),
	next_run: z.string().nullable().optional(),
	last_run: z.string().nullable().optional()
});
const ScheduleList = z.array(Schedule);
export type Schedule = z.infer<typeof Schedule>;

// ─── exports ────────────────────────────────────────────────────────────────

export type Connector = z.infer<typeof Connector>;
export type MemoryEntry = z.infer<typeof MemoryEntry>;
export type AgentRoster = z.infer<typeof AgentRoster>;
export type WeatherCurrent = z.infer<typeof WeatherCurrent>;

export const api = {
	health: () => request('/health', z.object({ status: z.string() })),

	connectors: {
		list: () => request('/api/connectors', ConnectorList),
		health: () => request('/api/connectors/health', HealthMap)
	},

	agents: {
		list: () => request('/api/agents', AgentList),
		get: (taskType: string) => request(`/api/agents/${taskType}`, AgentRoster)
	},

	memory: {
		list: () => request('/api/memory', MemoryList),
		get: (filename: string) => request(`/api/memory/${filename}`, MemoryEntry),
		index: () => request('/api/memory/index', z.object({ index: z.string() }))
	},

	weather: {
		current: () => request('/api/weather/current', WeatherCurrent)
	},

	notebook: {
		list: (path = '') => request(`/api/notebook/list?path=${encodeURIComponent(path)}`, z.object({ path: z.string(), entries: z.array(z.string()) })),
		read: (path: string) => request(`/api/notebook/read?path=${encodeURIComponent(path)}`, z.object({ path: z.string(), body: z.string() })),
		search: (q: string, path?: string) => {
			const params = new URLSearchParams({ q });
			if (path) params.set('path', path);
			return request(`/api/notebook/search?${params}`, z.array(z.object({ path: z.string(), line_number: z.number(), line: z.string() })));
		},
		counts: () => request('/api/notebook/counts', z.object({ log: z.number(), wiki: z.number(), fields: z.number(), people: z.number(), collections: z.number() })),
		updateCheckbox: (path: string, line: number, marker: string) =>
			request('/api/notebook/checkbox', z.object({ path: z.string(), line: z.number(), marker: z.string() }), {
				method: 'PATCH',
				body: JSON.stringify({ path, line, marker })
			})
	},

	tasks: {
		list: (filters?: { status?: string; type?: string }) => {
			const q = new URLSearchParams();
			if (filters?.status) q.set('status', filters.status);
			if (filters?.type) q.set('type', filters.type);
			const suffix = q.toString() ? `?${q}` : '';
			return request(`/api/tasks${suffix}`, z.array(Task));
		},
		get: (id: string) => request(`/api/tasks/${id}`, Task),
		create: (input: { type: string; title: string; description: string; repo?: string | null }) =>
			request('/api/tasks', Task, {
				method: 'POST',
				body: JSON.stringify(input)
			}),
		cancel: (id: string) => request(`/api/tasks/${id}/cancel`, Task, { method: 'POST' }),
		approve: (id: string) => request(`/api/tasks/${id}/approve`, Task, { method: 'POST' }),
		reject: (id: string) => request(`/api/tasks/${id}/reject`, Task, { method: 'POST' }),
		retry: (id: string) => request(`/api/tasks/${id}/retry`, Task, { method: 'POST' }),
		followUp: (id: string, prompt: string) =>
			request(`/api/tasks/${id}/follow-up`, Task, {
				method: 'POST',
				body: JSON.stringify({ prompt })
			})
	},

	repos: {
		list: () => request('/api/repos', RepoList),
		get: (name: string) => request(`/api/repos/${name}`, Repo),
		clone: (url: string) => request('/api/repos/clone', Repo, {
			method: 'POST',
			body: JSON.stringify({ url })
		})
	},

	projects: {
		list: () => request('/api/projects', ProjectList)
	},

	schedules: {
		list: () => request('/api/schedules', ScheduleList)
	}
};

export { ApiError };
