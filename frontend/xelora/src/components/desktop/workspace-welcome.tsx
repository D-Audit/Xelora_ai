'use client';
import { useState } from 'react';
import { FolderOpen, FilePlus2, ArrowRight, Sparkles, Loader2, Clock, CheckCircle2, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatRelativeTime } from '@/lib/utils';
import type { DesktopTask } from './types';
import type { User } from '@/types';
import { toast } from 'sonner';

const suggestions = [
  'Clean a spreadsheet',
  'Create a monthly report',
  'Explain a formula',
  'Find duplicate records',
  'Summarise sales by region',
  'Build a reusable workflow',
];

const statusIcon: Record<string, React.FC<{ className?: string }>> = {
  running: Loader2,
  awaiting_approval: AlertTriangle,
  completed: CheckCircle2,
  failed: AlertTriangle,
};
const statusColour: Record<string, string> = {
  running: 'text-xelora-info',
  awaiting_approval: 'text-amber-500',
  completed: 'text-xelora-success',
  failed: 'text-xelora-error',
};

interface Props {
  user: User | null;
  tasks: DesktopTask[];
  onSelectTask: (t: DesktopTask) => void;
  onOpenSpreadsheet: (name: string) => void;
}

export function WelcomeWorkspace({ user, tasks, onSelectTask, onOpenSpreadsheet }: Props) {
  const [input, setInput] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const firstName = user?.name?.split(' ')[0] ?? 'there';

  const handleSubmit = async (text: string) => {
    if (!text.trim()) return;
    setSubmitting(true);
    await new Promise(r => setTimeout(r, 400));
    setSubmitting(false);
    toast.info('Open a workbook first, then describe your task in the thread.');
    setInput('');
  };

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-white">
      <div className="flex flex-1 flex-col items-center justify-center px-6 py-12 text-center max-w-2xl mx-auto w-full">
        <h1 className="text-2xl font-semibold text-xelora-text">
          What would you like to do with your spreadsheet?
        </h1>
        <p className="mt-2 text-sm text-xelora-text-secondary">
          Open a workbook or describe the task you want Xelora to complete.
        </p>

        {/* Composer */}
        <div className="mt-8 w-full rounded-xl border border-xelora-border bg-white shadow-sm overflow-hidden">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(input); } }}
            placeholder="Describe the spreadsheet work you need…"
            rows={3}
            className="w-full resize-none px-4 pt-4 pb-2 text-sm text-xelora-text placeholder:text-xelora-text-muted focus:outline-none"
          />
          <div className="flex items-center justify-between border-t border-xelora-border px-3 py-2">
            <div className="flex gap-2">
              <button
                onClick={() => onOpenSpreadsheet('Sales_Q3_2026.xlsx')}
                className="flex items-center gap-1.5 rounded-md border border-xelora-border px-2.5 py-1.5 text-xs text-xelora-text-secondary hover:bg-xelora-surface-2 transition-colors"
              >
                <FolderOpen className="h-3.5 w-3.5" />
                Open Spreadsheet
              </button>
              <button
                onClick={() => toast.info('CSV import would open a file picker.')}
                className="flex items-center gap-1.5 rounded-md border border-xelora-border px-2.5 py-1.5 text-xs text-xelora-text-secondary hover:bg-xelora-surface-2 transition-colors"
              >
                <FilePlus2 className="h-3.5 w-3.5" />
                Import CSV
              </button>
            </div>
            <button
              onClick={() => handleSubmit(input)}
              disabled={!input.trim() || submitting}
              className="flex items-center gap-1.5 rounded-md bg-xelora-green px-3 py-1.5 text-xs font-medium text-white hover:bg-xelora-deep-green disabled:opacity-40 transition-colors"
            >
              {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ArrowRight className="h-3.5 w-3.5" />}
              Send
            </button>
          </div>
        </div>

        {/* Suggestions */}
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          {suggestions.map(s => (
            <button
              key={s}
              onClick={() => setInput(s)}
              className="rounded-full border border-xelora-border px-3 py-1.5 text-xs text-xelora-text-secondary hover:border-xelora-green hover:text-xelora-green transition-colors"
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Recent tasks */}
      {tasks.length > 0 && (
        <div className="border-t border-xelora-border px-6 py-5 max-w-2xl mx-auto w-full">
          <p className="text-xs font-semibold uppercase tracking-wider text-xelora-text-muted mb-3">Recent tasks</p>
          <div className="space-y-1">
            {tasks.slice(0, 5).map(task => {
              const Icon = statusIcon[task.status] ?? Sparkles;
              const colour = statusColour[task.status] ?? 'text-xelora-text-muted';
              return (
                <button
                  key={task.id}
                  onClick={() => onSelectTask(task)}
                  className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left hover:bg-xelora-surface-2 transition-colors"
                >
                  <Icon className={cn('h-4 w-4 shrink-0', colour, task.status === 'running' && 'animate-spin')} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-xelora-text truncate">{task.title}</p>
                    <p className="text-xs text-xelora-text-muted">{task.workbook} · {formatRelativeTime(task.updatedAt)}</p>
                  </div>
                  <ArrowRight className="h-3.5 w-3.5 text-xelora-text-muted shrink-0" />
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
