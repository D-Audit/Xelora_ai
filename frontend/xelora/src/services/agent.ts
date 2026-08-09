/**
 * Client-side service for the AI agent task endpoints. Calls our own
 * Next.js API routes (never the backend directly), which forward the
 * request server-side with the session cookie's JWT.
 */

export interface TaskStartResponse {
  task_id: number;
  status: string;
  message: string;
}

export interface TaskProgressResponse {
  task_id?: number;
  current_task: string;
  completed_action_count: number;
  completed_actions: { tool_name: string; execution_layer?: string }[];
  decision_explanations: string[];
  is_done: boolean;
  is_paused?: boolean;
  progress_log?: string[];
  final_response?: string | null;
}

export interface TaskRevealResponse {
  task_id: number;
  workflow: {
    step: number;
    native_feature: string;
    tool_name: string;
    execution_layer?: string;
    succeeded: boolean;
  }[];
  final_response?: string | null;
  is_done?: boolean;
  is_paused?: boolean;
}

export interface TaskStatusResponse {
  task_id: number;
  is_done: boolean;
  is_paused: boolean;
  status: 'running' | 'paused' | 'done';
  progress_log: string[];
  final_response?: string | null;
}

async function parseOrThrow<T>(res: Response): Promise<T> {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error((data as { error?: string }).error || 'Request failed.');
  }
  return data as T;
}

export async function startTask(instruction: string, workbookName?: string): Promise<TaskStartResponse> {
  const res = await fetch('/api/task', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ instruction, workbookName }),
  });
  return parseOrThrow<TaskStartResponse>(res);
}

export async function getTaskProgress(taskId: number): Promise<TaskProgressResponse> {
  const res = await fetch(`/api/task/${taskId}/progress`, { cache: 'no-store' });
  return parseOrThrow<TaskProgressResponse>(res);
}

export async function getTaskReveal(taskId: number): Promise<TaskRevealResponse> {
  const res = await fetch(`/api/task/${taskId}/reveal`, { cache: 'no-store' });
  return parseOrThrow<TaskRevealResponse>(res);
}

export async function getTaskStatus(taskId: number): Promise<TaskStatusResponse> {
  const res = await fetch(`/api/task/${taskId}/status`, { cache: 'no-store' });
  return parseOrThrow<TaskStatusResponse>(res);
}

export async function pauseTask(taskId: number) {
  const res = await fetch(`/api/task/${taskId}/pause`, { method: 'POST' });
  return parseOrThrow(res);
}

export async function resumeTask(taskId: number, correction?: string) {
  const res = await fetch(`/api/task/${taskId}/resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ correction }),
  });
  return parseOrThrow(res);
}
