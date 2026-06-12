export type TaskStatus =
  | "queued"
  | "triaging"
  | "executing"
  | "verifying"
  | "delivering"
  | "completed"
  | "failed";

export type TaskType = "code" | "triage";

export type TaskSource = "linear" | "chat" | "schedule" | "webhook";

export interface Task {
  id: string;
  type: TaskType | string;
  status: TaskStatus;
  source: TaskSource;
  source_id: string | null;
  repo: string | null;
  title: string;
  description: string;
  handler_data: Record<string, unknown>;
  result: Record<string, unknown> | null;
  retries: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface CreateTaskRequest {
  type: string;
  title: string;
  description: string;
  repo?: string;
  source_id?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  task_id: string | null;
  created_at: string;
}

export interface Schedule {
  id: string;
  name: string;
  cron_expr: string;
  task_type: string;
  task_template: Record<string, unknown>;
  enabled: boolean;
  last_run: string | null;
  next_run: string;
}

export interface CreateScheduleRequest {
  name: string;
  cron_expr: string;
  task_type: string;
  task_template?: Record<string, unknown>;
}

export interface HealthResponse {
  status: string;
}
