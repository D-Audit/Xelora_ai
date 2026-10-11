/** Browser client for the Next.js task proxies.  Keep these paths in sync with
 * src/app/api/task and src/app/api/tasks; the browser must never call FastAPI
 * directly because the session token is held in an httpOnly cookie. */

export interface ChatSummary {
  id: number;
  title: string;
  status: string;
  created_at: string | null;
  completed_at: string | null;
  is_read: boolean;
}

export interface ChatDetail {
  id: number;
  instruction: string;
  status: string;
  created_at: string | null;
  completed_at: string | null;
  transcript: { role: 'user' | 'assistant'; text: string; timestamp: string }[];
  resumable: boolean;
}

export interface TaskProgressResponse {
  task_id: number;
  is_done: boolean;
  is_paused: boolean;
  status: 'running' | 'paused' | 'awaiting_approval' | 'completed' | 'completed_with_warnings' | 'failed';
  current_task?: string;
  completed_actions?: { tool_name: string }[];
  visual_checkpoints?: { after_tool: string; filename: string }[];
  recovery?: {
    phase: string;
    message: string;
    tool_name?: string | null;
    safe_to_continue: boolean;
  } | null;
  progress_log: string[];
  final_response: string | null;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error((body as { error?: string; detail?: string }).error
      || (body as { detail?: string }).detail
      || 'Request to Xelora agent failed.');
  }
  return body as T;
}

export const listChats = () => request<ChatSummary[]>('/api/tasks');
export const getChat = (taskId: number) => request<ChatDetail>(`/api/tasks/${taskId}`);
export const markChatRead = (taskId: number) =>
  request<{ id: number; is_read: boolean }>(`/api/tasks/${taskId}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'mark-read' }),
  });
export const deleteChat = (taskId: number) =>
  request<{ id: number; deleted: boolean }>(`/api/tasks/${taskId}`, { method: 'DELETE' });

export const startTask = (instruction: string, workbookName?: string) =>
  request<{ task_id: number; status: string }>('/api/task', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ instruction, workbookName: workbookName ?? null }),
  });
export const resumeTask = (taskId: number, correction?: string) =>
  request<{ task_id: number; status: string }>(`/api/task/${taskId}/resume`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ correction: correction ?? null }),
  });
export const pauseTask = (taskId: number) =>
  request<{ task_id: number; is_paused: boolean }>(`/api/task/${taskId}/pause`, { method: 'POST' });
export const getTaskProgress = (taskId: number) =>
  request<TaskProgressResponse>(`/api/task/${taskId}/progress`);
export const getTaskReveal = (taskId: number) => request(`/api/task/${taskId}/reveal`);

export type BackendTaskSummary = ChatSummary;
export type BackendTaskDetail = ChatDetail;
export type BackendProgress = TaskProgressResponse;
export const listTasks = listChats;
export const getTaskDetail = getChat;
export const getProgress = getTaskProgress;

export function pollProgress(taskId: number, onUpdate: (snapshot: TaskProgressResponse) => void, intervalMs = 1500): () => void {
  let cancelled = false;
  const tick = async () => {
    if (cancelled) return;
    try {
      const snapshot = await getTaskProgress(taskId);
      if (cancelled) return;
      onUpdate(snapshot);
      if (!snapshot.is_done && !snapshot.is_paused) window.setTimeout(tick, intervalMs);
    } catch {
      if (!cancelled) window.setTimeout(tick, intervalMs * 2);
    }
  };
  void tick();
  return () => { cancelled = true; };
}
