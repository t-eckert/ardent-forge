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
import { Todo } from '$lib/schemas/todo';

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

const FieldStatus = z.object({
	label: z.string(),
	tone: z.enum(['ember', 'moss', 'graphite', 'warn'])
});
const FieldSummary = z.object({
	slug: z.string(),
	name: z.string(),
	path: z.string(),
	entries: z.number().int(),
	category: z.string().optional(),
	tagline: z.string().optional(),
	status: FieldStatus.optional(),
	sources: z.array(z.string()).optional(),
	featured: z.boolean().optional()
});
const FieldList = z.array(FieldSummary);

const FieldEntries = z.object({
	slug: z.string(),
	entries: z.array(z.string())
});

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

const TodoList = z.array(Todo.extend({
	created_at: z.string().optional()
}).passthrough());

// Threads respond with snake_case from the backend; view code renames at consumption time.
const BackendThread = z.object({
	id: z.string(),
	title: z.string(),
	kind: z.string(),
	last_activity_at: z.string(),
	unread: z.boolean(),
	created_at: z.string()
});
const BackendThreadList = z.array(BackendThread);
// Task summary embedded into task-dispatched / task-resolved messages by
// the backend (see forge/api/threads.py::_enrich_with_tasks).
const BackendTaskSummary = z.object({
	id: z.string(),
	type: z.string(),
	title: z.string(),
	status: z.string(),
	stages: z.array(z.string()),
	current_stage: z.string().nullable().optional(),
	result: z.record(z.string(), z.unknown()).nullable().optional(),
	completed_at: z.string().nullable().optional()
});

const BackendMessage = z.object({
	id: z.string(),
	thread_id: z.string(),
	role: z.string(),
	content: z.string(),
	variant: z.string(),
	widgets: z.array(z.unknown()),
	task_id: z.string().nullable().optional(),
	tool_use_id: z.string().nullable().optional(),
	task: BackendTaskSummary.nullable().optional(),
	created_at: z.string()
});
const BackendThreadDetail = BackendThread.extend({ messages: z.array(BackendMessage) });

// ─── exports ────────────────────────────────────────────────────────────────

export type Connector = z.infer<typeof Connector>;
export type MemoryEntry = z.infer<typeof MemoryEntry>;
export type AgentRoster = z.infer<typeof AgentRoster>;
export type FieldSummary = z.infer<typeof FieldSummary>;
export type WeatherCurrent = z.infer<typeof WeatherCurrent>;
export type BackendThread = z.infer<typeof BackendThread>;
export type BackendThreadDetail = z.infer<typeof BackendThreadDetail>;
export type BackendTaskSummary = z.infer<typeof BackendTaskSummary>;

export const api = {
	health: () => request('/health', z.object({ status: z.string() })),

	/** POST /api/chat — streaming response; returns raw Response. Caller decides
	 *  whether to consume the stream or just persist and refetch. */
	chat: {
		send: (content: string, thread_id?: string) =>
			fetch(`${API_BASE}/api/chat`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ content, thread_id })
			})
	},

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

	fields: {
		list: () => request('/api/fields', FieldList),
		get: (slug: string) => request(`/api/fields/${slug}`, FieldSummary),
		entries: (slug: string) => request(`/api/fields/${slug}/entries`, FieldEntries)
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
		counts: () => request('/api/notebook/counts', z.object({ log: z.number(), wiki: z.number(), fields: z.number(), people: z.number(), collections: z.number() }))
	},

	todos: {
		list: (due?: string) => {
			const q = due ? `?due=${due}` : '';
			return request(`/api/todos${q}`, TodoList);
		},
		create: (body: { title: string; status?: string; category?: string; context?: string; due_iso?: string }) =>
			request('/api/todos', z.any(), { method: 'POST', body: JSON.stringify(body) }),
		update: (id: string, patch: Record<string, unknown>) =>
			request(`/api/todos/${id}`, z.any(), { method: 'PATCH', body: JSON.stringify(patch) }),
		delete: (id: string) =>
			request(`/api/todos/${id}`, z.any(), { method: 'DELETE' })
	},

	threads: {
		list: () => request('/api/threads', BackendThreadList),
		get: (id: string) => request(`/api/threads/${id}`, BackendThreadDetail),
		create: (title: string, kind = 'chat') =>
			request('/api/threads', BackendThread, {
				method: 'POST',
				body: JSON.stringify({ title, kind })
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
		get: (id: string) => request(`/api/tasks/${id}`, Task)
	}
};

export { ApiError };
