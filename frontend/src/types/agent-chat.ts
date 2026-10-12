
export interface ChatSource {
  n: number;
  title: string;
  url: string;
}

export type ChatMessage =
  | { id: string; role: 'user'; text: string; attachment?: string }
  | {
      id: string;
      role: 'agent';
      taskId: number;
      steps: string[];
      currentTask?: string;
      response?: string;
      completionStatus?: string;
      /** 'chat' = a quick answer (no Excel task); omitted for workbook tasks. */
      kind?: 'chat' | 'task';
      sources?: ChatSource[];
      status: 'running' | 'paused' | 'done' | 'error';
      error?: string;
    };
