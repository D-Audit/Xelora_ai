'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Plus, Play, Trash2, GitBranch, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { StatePanel } from '@/components/site/state-panel';
import { getWorkflows, deleteWorkflow, runWorkflow } from '@/services/workspace';
import type { WorkflowItem } from '@/services/workspace';
import { formatRelativeTime } from '@/lib/utils';

const statusVariant: Record<string, 'default' | 'success' | 'info' | 'warning'> = {
  draft: 'default',
  published: 'success',
  archived: 'default',
  running: 'info',
};

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<WorkflowItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningId, setRunningId] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    getWorkflows()
      .then(setWorkflows)
      .catch((err) => toast.error(err instanceof Error ? err.message : 'Could not load workflows.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleDelete = async (w: WorkflowItem) => {
    try {
      await deleteWorkflow(w.id);
      setWorkflows((current) => current.filter((x) => x.id !== w.id));
      toast.success(`Deleted '${w.name}'.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not delete workflow.');
    }
  };

  const handleRun = async (w: WorkflowItem) => {
    setRunningId(w.id);
    try {
      const run = await runWorkflow(w.id);
      toast.success(`'${w.name}' started - task #${run.taskId}.`);
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not start this workflow.');
    } finally {
      setRunningId(null);
    }
  };

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Workflows"
        title="Saved workflows"
        description="Build a reusable, multi-step workflow once and run it whenever you need it. Running one submits it to the real AI agent and counts against your plan's workflow-run limit."
        actions={
          <Button asChild>
            <Link href="/dashboard/workflows/new"><Plus className="h-4 w-4" /> New workflow</Link>
          </Button>
        }
      />

      {loading ? (
        <StatePanel kind="loading" title="Loading workflows" description="Fetching your saved workflows." />
      ) : workflows.length === 0 ? (
        <StatePanel
          kind="empty"
          title="No workflows yet"
          description="Create your first workflow, or start from a template."
          actionLabel="New workflow"
          onAction={() => (window.location.href = '/dashboard/workflows/new')}
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {workflows.map((w) => (
            <Card key={w.id} className="p-5">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-md bg-xelora-surface-2">
                    <GitBranch className="h-5 w-5 text-xelora-green" />
                  </div>
                  <div>
                    <Link href={`/dashboard/workflows/${w.id}`} className="text-sm font-semibold text-xelora-text hover:text-xelora-green">
                      {w.name}
                    </Link>
                    <p className="line-clamp-2 text-xs text-xelora-text-muted">{w.description}</p>
                  </div>
                </div>
                <Badge variant={statusVariant[w.status] ?? 'default'}>{w.status}</Badge>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-xelora-text-secondary">
                <div>{w.steps.length} step{w.steps.length === 1 ? '' : 's'}</div>
                <div>{w.totalRuns} run{w.totalRuns === 1 ? '' : 's'}</div>
                <div className="col-span-2">Last run: {w.lastRunAt ? formatRelativeTime(w.lastRunAt) : 'never'}</div>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button size="sm" onClick={() => handleRun(w)} disabled={runningId === w.id}>
                  {runningId === w.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                  Run
                </Button>
                <Button size="sm" variant="ghost" className="text-xelora-error" onClick={() => handleDelete(w)}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
