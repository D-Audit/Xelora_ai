'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { StatePanel } from '@/components/site/state-panel';
import { getRunById, type WorkflowRunItem } from '@/services/workspace';
import { formatDate, formatRelativeTime } from '@/lib/utils';

export default function HistoryDetailPage() {
  const params = useParams<{ id: string }>();
  const [run, setRun] = useState<WorkflowRunItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getRunById(params.id).then(setRun).catch((err) => setError(err instanceof Error ? err.message : 'Run not found.')).finally(() => setLoading(false));
  }, [params.id]);

  if (loading) return <StatePanel kind="loading" title="Loading run details" description="Retrieving the persisted workflow run." />;
  if (!run || error) return <StatePanel kind="empty" title="Run not found" description={error || 'This workflow run does not exist.'} />;

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Automation history"
        title={run.workflowName || 'Workflow run'}
        description={`Started ${run.startedAt ? formatRelativeTime(run.startedAt) : 'at an unknown time'} · ${run.completedAt ? `completed ${formatDate(run.completedAt)}` : 'in progress'}`}
        actions={run.taskId ? <Button variant="outline" onClick={() => window.location.assign(`/dashboard/agent?task=${run.taskId}`)}>Open task</Button> : undefined}
      />
      <div className="grid gap-6 lg:grid-cols-[1fr_.8fr]">
        <Card className="p-5">
          <div className="flex flex-wrap gap-2">
            <Badge variant={run.status === 'completed' ? 'success' : run.status === 'failed' ? 'error' : 'info'}>{run.status.replaceAll('_', ' ')}</Badge>
            <Badge variant="outline">{run.stepsCompleted}/{run.totalSteps} steps</Badge>
            <Badge variant="outline">{run.aiActionsUsed} AI actions</Badge>
          </div>
          <div className="mt-5 rounded-lg border border-xelora-border p-4">
            <p className="text-xs uppercase tracking-wide text-xelora-text-muted">{run.startedAt ? formatRelativeTime(run.startedAt) : 'Start time unavailable'}</p>
            <p className="mt-1 text-sm text-xelora-text-secondary">The persisted workflow run is currently {run.status.replaceAll('_', ' ')}. Detailed actions are available from the linked agent task.</p>
          </div>
        </Card>
        <Card className="p-5">
          <h2 className="text-base font-semibold text-xelora-text">Run summary</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between gap-4"><dt className="text-xelora-text-muted">Duration</dt><dd>{run.durationSeconds ? `${Math.round(run.durationSeconds / 60)} min` : 'Running'}</dd></div>
            <div className="flex justify-between gap-4"><dt className="text-xelora-text-muted">Task</dt><dd>{run.taskId ? `#${run.taskId}` : 'Not linked'}</dd></div>
            <div className="flex justify-between gap-4"><dt className="text-xelora-text-muted">Workflow</dt><dd>{run.workflowName}</dd></div>
            <div className="flex justify-between gap-4"><dt className="text-xelora-text-muted">Output</dt><dd>Original workbook</dd></div>
          </dl>
        </Card>
      </div>
    </div>
  );
}
