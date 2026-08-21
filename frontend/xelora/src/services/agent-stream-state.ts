import type { TaskStreamEvent } from './agent';

export interface AgentStreamState {
  response?: string;
  streaming?: boolean;
  status: 'running' | 'paused' | 'done' | 'error';
  error?: string;
  steps: string[];
  currentTask?: string;
}

export function applyTaskStreamEvent<T extends AgentStreamState>(state: T, event: TaskStreamEvent): T {
  switch (event.type) {
    case 'assistant_started':
      return { ...state, streaming: true, error: undefined };
    case 'assistant_delta':
      return { ...state, response: (state.response ?? '') + event.content, streaming: true };
    case 'assistant_completed':
      return { ...state, streaming: false };
    case 'action_started':
      return { ...state, currentTask: event.label };
    case 'action_completed':
      return { ...state, steps: [...state.steps, event.label], currentTask: undefined };
    case 'action_failed':
      return { ...state, currentTask: undefined, error: `${event.label} failed.` };
    case 'awaiting_approval':
      return { ...state, status: 'done', streaming: false };
    case 'task_completed':
      return { ...state, status: 'done', streaming: false, response: event.content };
    case 'task_failed':
    case 'error':
      return { ...state, status: 'error', streaming: false, error: event.message };
    default:
      return state;
  }
}
