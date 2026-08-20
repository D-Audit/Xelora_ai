'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Search, Filter, CheckCircle2, AlertTriangle, XCircle, PauseCircle, CircleHelp } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { StatePanel } from '@/components/site/state-panel';
import { getWorkflowRuns, type WorkflowRunItem } from '@/services/workspace';
import { formatDate, formatRelativeTime } from '@/lib/utils';

const statusMap: Record<string, { label: string; variant: 'success' | 'warning' | 'error' | 'info' | 'default'; icon: React.ComponentType<{ className?: string }> }> = {
  completed: { label: 'Completed', variant: 'success', icon: CheckCircle2 },
  completed_with_warnings: { label: 'Warnings', variant: 'warning', icon: AlertTriangle },
  failed: { label: 'Failed', variant: 'error', icon: XCircle },
  cancelled: { label: 'Cancelled', variant: 'default', icon: XCircle },
  paused: { label: 'Paused', variant: 'info', icon: PauseCircle },
  awaiting_approval: { label: 'Awaiting approval', variant: 'info', icon: CircleHelp },
  running: { label: 'Running', variant: 'info', icon: CircleHelp },
};

const statusFilters = ['all', 'completed', 'completed_with_warnings', 'failed', 'cancelled', 'paused', 'awaiting_approval'] as const;

export default function HistoryPage() {
  const [runs, setRuns] = useState<WorkflowRunItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<(typeof statusFilters)[number]>('all');

  useEffect(() => {
    getWorkflowRuns().then((data) => {
      setRuns(data);
      setLoading(false);
    });
  }, []);

  const filtered = useMemo(() => {
    return runs.filter((run) => {
      const matchesSearch = run.workflowName.toLowerCase().includes(search.toLowerCase());
      const matchesStatus = status === 'all' || run.status === status;
      return matchesSearch && matchesStatus;
    });
  }, [runs, search, status]);

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Automation history"
        title="Review past workflow runs"
        description="Each row shows the workbook, workflow, usage, and current result state."
      />

      <Card className="p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="relative w-full lg:max-w-sm">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-xelora-text-muted" />
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search history" className="pl-9" />
          </div>
          <div className="flex flex-wrap gap-2">
            {statusFilters.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setStatus(item)}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                  status === item ? 'border-xelora-green bg-xelora-success-bg text-xelora-success' : 'border-xelora-border bg-white text-xelora-text-secondary hover:bg-xelora-surface-2'
                }`}
              >
                <Filter className="mr-1.5 inline h-3.5 w-3.5" />
                {item === 'all' ? 'All runs' : item.replace('_', ' ')}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {loading ? (
        <StatePanel kind="loading" title="Loading history" description="Retrieving your automation runs." />
      ) : filtered.length === 0 ? (
        <StatePanel kind="empty" title="No history found" description="Try a different search term or filter." />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-xelora-surface-2">
                <tr className="border-b border-xelora-border text-left">
                  <th className="px-5 py-3 font-medium text-xelora-text-secondary">Workbook</th>
                  <th className="px-4 py-3 font-medium text-xelora-text-secondary">Workflow</th>
                  <th className="px-4 py-3 font-medium text-xelora-text-secondary">User</th>
                  <th className="px-4 py-3 font-medium text-xelora-text-secondary">Date</th>
                  <th className="px-4 py-3 font-medium text-xelora-text-secondary">Steps</th>
                  <th className="px-4 py-3 font-medium text-xelora-text-secondary">Usage</th>
                  <th className="px-4 py-3 font-medium text-xelora-text-secondary">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-xelora-border bg-white">
                {filtered.map((run) => {
                  const config = statusMap[run.status] ?? statusMap.running;
                  const StatusIcon = config.icon;
                  return (
                    <tr key={run.id} className="hover:bg-xelora-surface-2">
                      <td className="px-5 py-3">
                        <Link href={`/dashboard/history/${run.id}`} className="font-medium text-xelora-text hover:text-xelora-green">
                          {run.workflowName || 'Workflow run'}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-xelora-text-secondary">{run.workflowName}</td>
                      <td className="px-4 py-3 text-xelora-text-secondary">Current user</td>
                      <td className="px-4 py-3 text-xelora-text-secondary">{run.startedAt ? formatDate(run.startedAt) : 'Unknown'}</td>
                      <td className="px-4 py-3 text-xelora-text-secondary">{run.stepsCompleted}/{run.totalSteps}</td>
                      <td className="px-4 py-3 text-xelora-text-secondary">{run.aiActionsUsed} AI actions</td>
                      <td className="px-4 py-3">
                        <Badge variant={config.variant}>
                          <StatusIcon className="mr-1 h-3.5 w-3.5" />
                          {config.label}
                        </Badge>
                        <p className="mt-1 text-xs text-xelora-text-muted">{run.startedAt ? formatRelativeTime(run.startedAt) : 'Unknown'}</p>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
