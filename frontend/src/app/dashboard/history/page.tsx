'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Search } from 'lucide-react';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { StatePanel } from '@/components/site/state-panel';
import { Input } from '@/components/ui/input';
import { listChats, type ChatSummary } from '@/services/agent';
import { getWorkflowRuns, type WorkflowRunItem } from '@/services/workspace';
import { formatRelativeTime } from '@/lib/utils';
import { cn } from '@/lib/utils';

const STATUS: Record<string, { label: string; tone: string }> = {
  completed: { label: 'Completed', tone: 'text-xelora-green' },
  answered: { label: 'Answered', tone: 'text-xelora-text-secondary' },
  completed_with_warnings: { label: 'Needs review', tone: 'text-xelora-warning' },
  awaiting_approval: { label: 'Waiting for you', tone: 'text-xelora-text-secondary' },
  running: { label: 'Running', tone: 'text-xelora-info' },
  paused: { label: 'Paused', tone: 'text-xelora-warning' },
  failed: { label: 'Not completed', tone: 'text-xelora-error' },
};

const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'completed', label: 'Completed' },
  { value: 'attention', label: 'Needs attention' },
] as const;

function StatusText({ status }: { status: string }) {
  const item = STATUS[status] ?? { label: status, tone: 'text-xelora-text-secondary' };
  return <span className={cn('text-xs font-medium', item.tone)}>{item.label}</span>;
}

export default function HistoryPage() {
  const [chats, setChats] = useState<ChatSummary[] | null>(null);
  const [runs, setRuns] = useState<WorkflowRunItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<(typeof FILTERS)[number]['value']>('all');

  useEffect(() => {
    listChats().then(setChats).catch((err) => setError(err instanceof Error ? err.message : 'Could not load your history.'));
    getWorkflowRuns().then(setRuns).catch(() => setRuns([]));
  }, []);

  const visible = useMemo(() => (chats ?? []).filter((chat) => {
    if (query && !chat.title.toLowerCase().includes(query.toLowerCase())) return false;
    if (filter === 'completed') return chat.status === 'completed' || chat.status === 'answered';
    if (filter === 'attention') return ['failed', 'completed_with_warnings', 'awaiting_approval', 'paused'].includes(chat.status);
    return true;
  }), [chats, query, filter]);

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <DashboardPageHeader title="Task history" description="Every conversation and task you have run with Xelora." />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-xelora-text-muted" />
          <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search your tasks" className="pl-9" aria-label="Search tasks" />
        </div>
        <div className="inline-flex rounded-lg border border-xelora-border bg-xelora-surface p-1">
          {FILTERS.map((item) => (
            <button
              key={item.value}
              type="button"
              onClick={() => setFilter(item.value)}
              aria-pressed={filter === item.value}
              className={cn('rounded-md px-3 py-1 text-sm transition-colors', filter === item.value ? 'bg-xelora-surface-2 font-medium text-xelora-text' : 'text-xelora-text-secondary hover:text-xelora-text')}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {error ? (
        <StatePanel kind="error" title="Could not load your history" description={error} />
      ) : chats === null ? (
        <StatePanel kind="loading" title="Loading your history" description="" />
      ) : visible.length === 0 ? (
        <StatePanel
          kind="empty"
          title={chats.length === 0 ? 'No tasks yet' : 'No matching tasks'}
          description={chats.length === 0 ? 'Start a chat and your tasks will be listed here.' : 'Try a different search or filter.'}
        />
      ) : (
        <ul className="divide-y divide-xelora-border overflow-hidden rounded-xl border border-xelora-border bg-xelora-surface">
          {visible.map((chat) => (
            <li key={chat.id}>
              <Link href={`/dashboard/agent?chat=${chat.id}`} className="flex items-center gap-4 px-4 py-3.5 transition-colors hover:bg-xelora-surface-2">
                <span className="min-w-0 flex-1 truncate text-sm text-xelora-text">{chat.title}</span>
                <StatusText status={chat.status} />
                <span className="hidden w-28 shrink-0 text-right text-xs text-xelora-text-muted sm:block">
                  {chat.created_at ? formatRelativeTime(chat.created_at) : ''}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {runs.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-xelora-text">Workflow runs</h2>
          <ul className="mt-3 divide-y divide-xelora-border overflow-hidden rounded-xl border border-xelora-border bg-xelora-surface">
            {runs.map((run) => (
              <li key={run.id}>
                <Link href={`/dashboard/workflows/${run.workflowId}`} className="flex items-center gap-4 px-4 py-3.5 transition-colors hover:bg-xelora-surface-2">
                  <span className="min-w-0 flex-1 truncate text-sm text-xelora-text">{run.workflowName}</span>
                  <span className="text-xs text-xelora-text-muted">{run.stepsCompleted}/{run.totalSteps} steps</span>
                  <StatusText status={run.status} />
                  <span className="hidden w-28 shrink-0 text-right text-xs text-xelora-text-muted sm:block">
                    {run.startedAt ? formatRelativeTime(run.startedAt) : ''}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
