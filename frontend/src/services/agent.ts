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
  transcript: {
    role: 'user' | 'assistant';
    text: string;
    timestamp?: string;
    /** 'chat' marks a quick answer (not an Excel task result). */
    kind?: 'chat';
    sources?: { n: number; title: string; url: string }[];
  }[];
  resumable: boolean;
}

export interface TaskProgressResponse {
  task_id: number;
  is_done: boolean;
  is_paused: boolean;
  /** 'answered' = replied directly (greeting or question), no Excel work. */
  status: 'running' | 'paused' | 'awaiting_approval' | 'completed' | 'completed_with_warnings' | 'failed' | 'answered';
  sources?: { n: number; title: string; url: string }[];
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

export interface QuickChatResponse {
  route: 'chat' | 'task';
  reason: string;
  reply: string | null;
  sources: { n: number; title: string; url: string }[];
  /** The conversation the answer was saved to (null when not signed in / no database). */
  task_id?: number | null;
  /** True when no model answered in time; the reply is an apology, not an answer. */
  failed?: boolean;
}

type QuickChatEvent =
  | { type: 'route'; route: 'chat' | 'task'; reason: string }
  | { type: 'status'; text: string }
  | { type: 'ping' }
  | ({ type: 'answer' } & Omit<QuickChatResponse, 'route' | 'reason'>);

/**
 * quickChat as a stream: onRoute fires as soon as the backend has decided
 * between a quick answer and an Excel task, onStatus with each live step
 * ("Searching the web for ..."). Resolves with the final answer; throws if
 * the connection fails or ends before an answer arrives.
 */
export async function quickChatStream(
  instruction: string,
  options: {
    workbookName?: string;
    hasWorkbookContext?: boolean;
    history?: { role: 'user' | 'assistant'; text: string }[];
    taskId?: number | null;
  },
  handlers: { onRoute?: (route: 'chat' | 'task') => void; onStatus?: (text: string) => void } = {},
): Promise<QuickChatResponse> {
  const response = await fetch('/api/chat/stream', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      instruction,
      workbookName: options.workbookName ?? null,
      hasWorkbookContext: Boolean(options.hasWorkbookContext),
      history: options.history ?? [],
      taskId: options.taskId ?? null,
    }),
  });
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => ({}));
    throw new Error((body as { error?: string }).error || 'Could not reach Xelora. Please try again.');
  }

  let route: { route: 'chat' | 'task'; reason: string } | null = null;
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (value) buffer += value;
    const lines = buffer.split('\n');
    buffer = done ? '' : lines.pop() ?? '';
    for (const line of lines) {
      if (!line.trim()) continue;
      let event: QuickChatEvent;
      try {
        event = JSON.parse(line) as QuickChatEvent;
      } catch {
        continue;
      }
      if (event.type === 'route') {
        route = { route: event.route, reason: event.reason };
        handlers.onRoute?.(event.route);
      } else if (event.type === 'status') {
        handlers.onStatus?.(event.text);
      } else if (event.type === 'answer' && route) {
        return { ...route, reply: event.reply, sources: event.sources ?? [], task_id: event.task_id, failed: event.failed };
      }
    }
    if (done) break;
  }
  if (route?.route === 'task') return { ...route, reply: null, sources: [] };
  throw new Error('The connection to Xelora closed before an answer arrived. Please try again.');
}

/** Quick answers (may search the web) for questions; route "task" means: start a workbook task instead. */
export const quickChat = (
  instruction: string,
  options: {
    workbookName?: string;
    hasWorkbookContext?: boolean;
    history?: { role: 'user' | 'assistant'; text: string }[];
    taskId?: number | null;
  } = {},
) =>
  request<QuickChatResponse>('/api/chat', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      instruction,
      workbookName: options.workbookName ?? null,
      hasWorkbookContext: Boolean(options.hasWorkbookContext),
      history: options.history ?? [],
      taskId: options.taskId ?? null,
    }),
  });

/** `routed`: the message already went through quick chat, which chose Excel work; don't re-route it. */
export const startTask = (instruction: string, workbookName?: string, routed = false) =>
  request<{ task_id: number; status: string }>('/api/task', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ instruction, workbookName: workbookName ?? null, routed }),
  });
export const resumeTask = (taskId: number, correction?: string, routed = false) =>
  request<{ task_id: number; status: string }>(`/api/task/${taskId}/resume`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ correction: correction ?? null, routed }),
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
