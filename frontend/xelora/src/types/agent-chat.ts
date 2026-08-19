
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
      status: 'running' | 'paused' | 'done' | 'error';
      error?: string;
    };
