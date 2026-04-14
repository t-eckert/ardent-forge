import type {
  Task,
  CreateTaskRequest,
  ChatMessage,
  Schedule,
  CreateScheduleRequest,
  HealthResponse,
} from "$lib/types";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/**
 * Base URL for all API requests.
 *
 * - In the deployed build: empty string. The UI is served from the same host
 *   as Forge, so relative paths (/api/...) just work.
 * - In local dev: set VITE_API_URL to point at the box over Tailscale,
 *   e.g. `VITE_API_URL=https://ardent-forge.<tailnet>.ts.net`. All requests
 *   get prefixed with this URL and hit the real backend.
 *
 * See memory/project_dev_process.md § Mode 2 — Hybrid.
 */
const API_BASE: string = (import.meta.env?.VITE_API_URL ?? "").replace(/\/$/, "");

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new ApiError(res.status, text);
  }
  return res.json();
}

export const api = {
  // Health
  health(): Promise<HealthResponse> {
    return request("/health");
  },

  // Tasks
  listTasks(status?: string): Promise<Task[]> {
    const params = status ? `?status=${status}` : "";
    return request(`/api/tasks${params}`);
  },

  getTask(id: string): Promise<Task> {
    return request(`/api/tasks/${id}`);
  },

  createTask(data: CreateTaskRequest): Promise<Task> {
    return request("/api/tasks", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  // Chat
  getMessages(): Promise<ChatMessage[]> {
    return request("/api/chat/messages");
  },

  clearMessages(): Promise<{ status: string }> {
    return request("/api/chat/messages", { method: "DELETE" });
  },

  async *sendMessage(content: string): AsyncGenerator<string> {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "Unknown error");
      throw new ApiError(res.status, text);
    }
    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      yield decoder.decode(value, { stream: true });
    }
  },

  // Schedules
  listSchedules(): Promise<Schedule[]> {
    return request("/api/schedules");
  },

  createSchedule(data: CreateScheduleRequest): Promise<Schedule> {
    return request("/api/schedules", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  deleteSchedule(id: string): Promise<void> {
    return request(`/api/schedules/${id}`, { method: "DELETE" });
  },

  toggleSchedule(id: string, enabled: boolean): Promise<Schedule> {
    return request(`/api/schedules/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    });
  },
};
