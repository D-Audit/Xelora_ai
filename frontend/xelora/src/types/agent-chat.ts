
export type ChatMessage =
  | { id: string; role: 'user'; text: string; attachment?: string }
  | {
      id: string;
      role: 'agent';
      taskId: number;
      steps: string[];
      currentTask?: string;
      response?: string;
      streaming?: boolean;
      status: 'running' | 'paused' | 'done' | 'error';
      error?: string;
    };
