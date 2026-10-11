'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { StatePanel } from '@/components/site/state-panel';
import { mockWorkflowRuns } from '@/data/mock-workflows';
import { formatDate, formatRelativeTime } from '@/lib/utils';

export default function HistoryDetailPage() {
  const params = useParams<{ id: string }>();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 400);
    return () => clearTimeout(timer);
  }, []);

  const run = useMemo(() => mockWorkflowRuns.find((item) => item.id === params.id), [params.id]);

  if (!loading && !run) {
    return <StatePanel kind="empty" title="Run not found" description="This mock workflow run is not part of the seeded dataset." />;
  }

  if (loading || !run) {
    return <StatePanel kind="loading" title="Loading run details" description="Retrieving the run timeline and summary." />;
  }

  const timeline = run.timeline ?? [];

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Automation history"
        title={run.workflowName}
        description={`${run.fileName} • started ${formatRelativeTime(run.startedAt)} • completed ${run.completedAt ? formatDate(run.completedAt) : 'in progress'}`}
        actions={<Button variant="outline">Open workbook</Button>}
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_.8fr]">
        <Card className="p-5">
          <div className="flex flex-wrap gap-2">
            <Badge variant="success">{run.status}</Badge>
            <Badge variant="outline">{run.stepsCompleted}/{run.totalSteps} steps</Badge>
            <Badge variant="outline">{run.aiActionsUsed} AI actions</Badge>
          </div>
          <div className="mt-5 space-y-3">
            {(timeline.length > 0 ? timeline : [{ id: 'empty', timestamp: run.startedAt, message: 'No timeline events were captured for this run.', type: 'info' as const }]).map((event) => (
              <div key={event.id} className="rounded-lg border border-xelora-border p-4">
                <p className="text-xs uppercase tracking-wide text-xelora-text-muted">{formatRelativeTime(event.timestamp)}</p>
                <p className="mt-1 text-sm text-xelora-text-secondary">{event.message}</p>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-5">
          <h2 className="text-base font-semibold text-xelora-text">Run summary</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-xelora-text-muted">Duration</dt>
              <dd className="text-xelora-text">{run.durationSeconds ? `${Math.round(run.durationSeconds / 60)} min` : 'Running'}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-xelora-text-muted">User</dt>
              <dd className="text-xelora-text">{run.userName}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-xelora-text-muted">Workbook</dt>
              <dd className="text-xelora-text">{run.fileName}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-xelora-text-muted">Output</dt>
              <dd className="text-xelora-text">{run.outputFileId ?? 'Same workbook'}</dd>
            </div>
          </dl>
        </Card>
      </div>
    </div>
  );
}
